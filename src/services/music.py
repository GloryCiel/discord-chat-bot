"""Per-guild music queues and playback orchestration."""

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import discord

from src.domain.music import Track
from src.integrations.media_extractor import MediaExtractor

logger = logging.getLogger(__name__)

FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTIONS = "-vn -loglevel warning"
AudioSourceFactory = Callable[[str], discord.AudioSource]


def create_audio_source(stream_url: str) -> discord.AudioSource:
    """Create an Opus audio source backed by the system FFmpeg binary."""
    return discord.FFmpegOpusAudio(
        stream_url,
        before_options=FFMPEG_BEFORE_OPTIONS,
        options=FFMPEG_OPTIONS,
    )


class VoiceChannel(Protocol):
    """Minimum Discord voice-channel interface used by the service."""

    id: int

    async def connect(self) -> "VoiceClient": ...


class VoiceClient(Protocol):
    """Minimum Discord voice-client interface used by the service."""

    channel: VoiceChannel

    def is_connected(self) -> bool: ...

    async def move_to(self, channel: VoiceChannel) -> None: ...

    def play(
        self,
        source: discord.AudioSource,
        *,
        after: Callable[[Exception | None], Any] | None = None,
    ) -> None: ...


class MusicQueueFullError(RuntimeError):
    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(f"음악 대기열은 최대 {limit}곡까지 추가할 수 있습니다.")


@dataclass(frozen=True)
class EnqueueResult:
    track: Track
    position: int


@dataclass(frozen=True)
class QueueSnapshot:
    current: Track | None
    queued: tuple[Track, ...]


@dataclass
class GuildMusicPlayer:
    """All mutable music state belonging to one Discord guild."""

    guild_id: int
    max_queue_size: int = 50
    queue: deque[Track] = field(default_factory=deque)
    current: Track | None = None
    voice_client: VoiceClient | None = None
    playback_task: asyncio.Task[None] | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def enqueue(self, track: Track) -> int:
        """Append a track and return its one-based queue position."""
        async with self.lock:
            if len(self.queue) >= self.max_queue_size:
                raise MusicQueueFullError(self.max_queue_size)
            self.queue.append(track)
            return len(self.queue)

    async def snapshot(self) -> QueueSnapshot:
        """Return an immutable view of the current track and queue."""
        async with self.lock:
            return QueueSnapshot(current=self.current, queued=tuple(self.queue))

    # TODO(MUSIC-8): Add an idle-disconnect task.


class MusicService:
    """Coordinate players without depending on slash-command responses."""

    def __init__(
        self,
        extractor: MediaExtractor,
        max_queue_size: int = 50,
        audio_source_factory: AudioSourceFactory = create_audio_source,
    ):
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be at least 1")
        self.extractor = extractor
        self.max_queue_size = max_queue_size
        self.audio_source_factory = audio_source_factory
        self._players: dict[int, GuildMusicPlayer] = {}

    def get_player(self, guild_id: int) -> GuildMusicPlayer:
        """Return the persistent in-memory player for one guild."""
        if guild_id not in self._players:
            self._players[guild_id] = GuildMusicPlayer(
                guild_id=guild_id,
                max_queue_size=self.max_queue_size,
            )
        return self._players[guild_id]

    async def enqueue(
        self, guild_id: int, query: str, requested_by: int
    ) -> EnqueueResult:
        """Resolve one public media query and append it to a guild queue."""
        track = await self.extractor.search(query, requested_by)
        player = self.get_player(guild_id)
        position = await player.enqueue(track)
        return EnqueueResult(track=track, position=position)

    async def queue_snapshot(self, guild_id: int) -> QueueSnapshot:
        return await self.get_player(guild_id).snapshot()

    async def connect(self, guild_id: int, channel: VoiceChannel) -> VoiceClient:
        """Connect to a voice channel or move the existing guild client."""
        player = self.get_player(guild_id)
        async with player.lock:
            voice_client = player.voice_client
            if voice_client is not None and voice_client.is_connected():
                if voice_client.channel.id != channel.id:
                    await voice_client.move_to(channel)
                return voice_client

            voice_client = await channel.connect()
            player.voice_client = voice_client
            return voice_client

    async def connected_channel_id(self, guild_id: int) -> int | None:
        """Return the connected channel ID, ignoring stale voice clients."""
        player = self.get_player(guild_id)
        async with player.lock:
            voice_client = player.voice_client
            if voice_client is None or not voice_client.is_connected():
                return None
            return voice_client.channel.id

    async def start_playback(self, guild_id: int) -> bool:
        """Start one guild playback worker if it is not already running."""
        player = self.get_player(guild_id)
        async with player.lock:
            if player.voice_client is None or not player.voice_client.is_connected():
                return False
            if player.playback_task is not None and not player.playback_task.done():
                return False
            if not player.queue:
                return False

            player.playback_task = asyncio.create_task(
                self._playback_worker(player),
                name=f"music-player-{guild_id}",
            )
            return True

    async def _playback_worker(self, player: GuildMusicPlayer) -> None:
        """Play queued tracks serially until the guild queue is empty."""
        try:
            while True:
                async with player.lock:
                    voice_client = player.voice_client
                    if (
                        voice_client is None
                        or not voice_client.is_connected()
                        or not player.queue
                    ):
                        player.current = None
                        return
                    track = player.queue.popleft()
                    player.current = track

                try:
                    await self._play_track(player, voice_client, track)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Failed to play track %r in guild %s",
                        track.title,
                        player.guild_id,
                    )
                finally:
                    async with player.lock:
                        if player.current is track:
                            player.current = None
        finally:
            async with player.lock:
                current_task = asyncio.current_task()
                if player.playback_task is current_task:
                    player.playback_task = None

    async def _play_track(
        self,
        player: GuildMusicPlayer,
        voice_client: VoiceClient,
        track: Track,
    ) -> None:
        stream_url = await self.extractor.get_stream_url(track)
        source = self.audio_source_factory(stream_url)
        finished = asyncio.Event()
        loop = asyncio.get_running_loop()

        def after_playback(error: Exception | None) -> None:
            if error is not None:
                logger.error(
                    "FFmpeg playback failed for %r in guild %s: %s",
                    track.title,
                    player.guild_id,
                    error,
                )
            loop.call_soon_threadsafe(finished.set)

        try:
            voice_client.play(source, after=after_playback)
        except Exception:
            source.cleanup()
            raise
        await finished.wait()

    # TODO(MUSIC-6): Implement pause, resume, skip, stop, and leave.
