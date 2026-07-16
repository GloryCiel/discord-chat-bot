"""Per-guild music queues and playback orchestration."""

import asyncio
from collections import deque
from dataclasses import dataclass, field

from src.domain.music import Track
from src.integrations.media_extractor import MediaExtractor


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

    # TODO(MUSIC-4): Store or receive the guild VoiceClient.
    # TODO(MUSIC-5): Add a playback worker and next-track signal.
    # TODO(MUSIC-8): Add an idle-disconnect task.


class MusicService:
    """Coordinate players without depending on slash-command responses."""

    def __init__(self, extractor: MediaExtractor, max_queue_size: int = 50):
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be at least 1")
        self.extractor = extractor
        self.max_queue_size = max_queue_size
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

    # TODO(MUSIC-5): Implement play_next, pause, resume, skip, stop, and leave.
