"""Per-guild music queues and playback orchestration."""

import asyncio
import contextlib
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
DEFAULT_IDLE_TIMEOUT_SECONDS = 300.0
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

    def is_playing(self) -> bool: ...

    def is_paused(self) -> bool: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...

    def stop(self) -> None: ...

    async def disconnect(self, *, force: bool = False) -> None: ...


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
    idle_disconnect_task: asyncio.Task[None] | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def enqueue(self, track: Track) -> int:
        """Append a track and return its one-based queue position."""
        async with self.lock:
            if len(self.queue) >= self.max_queue_size:
                raise MusicQueueFullError(self.max_queue_size)
            if self.idle_disconnect_task is not None:
                self.idle_disconnect_task.cancel()
                self.idle_disconnect_task = None
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
        idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS,
    ):
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be at least 1")
        if idle_timeout_seconds < 0:
            raise ValueError("idle_timeout_seconds cannot be negative")
        self.extractor = extractor
        self.max_queue_size = max_queue_size
        self.audio_source_factory = audio_source_factory
        self.idle_timeout_seconds = idle_timeout_seconds
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
        stale_task: asyncio.Task[None] | None = None
        async with player.lock:
            if player.idle_disconnect_task is not None:
                player.idle_disconnect_task.cancel()
                player.idle_disconnect_task = None
            voice_client = player.voice_client
            if voice_client is not None and voice_client.is_connected():
                if voice_client.channel.id != channel.id:
                    await voice_client.move_to(channel)
                return voice_client

            if player.playback_task is not None and not player.playback_task.done():
                stale_task = player.playback_task
                stale_task.cancel()
                player.playback_task = None
                player.current = None
            voice_client = await channel.connect()
            player.voice_client = voice_client
        if stale_task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await stale_task
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
            schedule_idle_disconnect = False
            async with player.lock:
                current_task = asyncio.current_task()
                if player.playback_task is current_task:
                    player.playback_task = None
                    schedule_idle_disconnect = (
                        player.voice_client is not None
                        and player.voice_client.is_connected()
                        and not player.queue
                    )
            if schedule_idle_disconnect:
                await self.schedule_idle_disconnect(player.guild_id)

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

    async def pause(self, guild_id: int) -> bool:
        """Pause active playback for one guild."""
        player = self.get_player(guild_id)
        async with player.lock:
            voice_client = player.voice_client
            if voice_client is None or not voice_client.is_playing():
                return False
            voice_client.pause()
            return True

    async def resume(self, guild_id: int) -> bool:
        """Resume paused playback for one guild."""
        player = self.get_player(guild_id)
        async with player.lock:
            voice_client = player.voice_client
            if voice_client is None or not voice_client.is_paused():
                return False
            voice_client.resume()
            return True

    async def skip(self, guild_id: int) -> Track | None:
        """Skip the current track and continue with the remaining queue."""
        player = self.get_player(guild_id)
        async with player.lock:
            track = player.current
            task = player.playback_task
            voice_client = player.voice_client
            if track is None or task is None or task.done():
                return None

        if voice_client is not None and (
            voice_client.is_playing() or voice_client.is_paused()
        ):
            voice_client.stop()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await self.start_playback(guild_id)
        return track

    async def stop(self, guild_id: int, *, schedule_idle: bool = True) -> bool:
        """Stop playback and clear the guild queue, keeping voice connected."""
        player = self.get_player(guild_id)
        async with player.lock:
            had_music = bool(
                player.current
                or player.queue
                or (
                    player.playback_task is not None and not player.playback_task.done()
                )
            )
            player.queue.clear()
            task = player.playback_task
            voice_client = player.voice_client

        if voice_client is not None and (
            voice_client.is_playing() or voice_client.is_paused()
        ):
            voice_client.stop()
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        if schedule_idle:
            await self.schedule_idle_disconnect(guild_id)
        return had_music

    async def leave(self, guild_id: int) -> bool:
        """Clear playback state and disconnect the guild voice client."""
        await self.stop(guild_id, schedule_idle=False)
        player = self.get_player(guild_id)
        async with player.lock:
            idle_task = player.idle_disconnect_task
            if idle_task is not None and idle_task is not asyncio.current_task():
                idle_task.cancel()
            player.idle_disconnect_task = None
            voice_client = player.voice_client
            player.voice_client = None
        if voice_client is None or not voice_client.is_connected():
            return False
        await voice_client.disconnect(force=True)
        return True

    async def schedule_idle_disconnect(
        self,
        guild_id: int,
        *,
        stop_playback: bool = False,
    ) -> bool:
        """Schedule a delayed disconnect for an empty queue or empty channel."""
        player = self.get_player(guild_id)
        async with player.lock:
            voice_client = player.voice_client
            if voice_client is None or not voice_client.is_connected():
                return False
            existing = player.idle_disconnect_task
            if existing is not None:
                existing.cancel()
            player.idle_disconnect_task = asyncio.create_task(
                self._idle_disconnect_worker(player, stop_playback=stop_playback),
                name=f"music-idle-{guild_id}",
            )
            return True

    async def cancel_idle_disconnect(self, guild_id: int) -> bool:
        """Cancel a guild's pending automatic disconnect."""
        player = self.get_player(guild_id)
        async with player.lock:
            task = player.idle_disconnect_task
            if task is None:
                return False
            task.cancel()
            player.idle_disconnect_task = None
            return True

    async def _idle_disconnect_worker(
        self,
        player: GuildMusicPlayer,
        *,
        stop_playback: bool,
    ) -> None:
        try:
            await asyncio.sleep(self.idle_timeout_seconds)
            async with player.lock:
                if not stop_playback and (player.current is not None or player.queue):
                    return
                if player.idle_disconnect_task is asyncio.current_task():
                    player.idle_disconnect_task = None
            await self.leave(player.guild_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Automatic voice disconnect failed in guild %s", player.guild_id
            )
        finally:
            async with player.lock:
                if player.idle_disconnect_task is asyncio.current_task():
                    player.idle_disconnect_task = None

    async def shutdown(self) -> None:
        """Cancel music tasks and disconnect all guild voice clients."""
        for guild_id in tuple(self._players):
            try:
                await self.leave(guild_id)
            except Exception:
                logger.exception("Music shutdown failed in guild %s", guild_id)
