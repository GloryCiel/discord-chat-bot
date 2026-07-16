"""Per-guild music queues and playback orchestration.

Work through TODO(MUSIC-3), TODO(MUSIC-4), TODO(MUSIC-5), and TODO(MUSIC-8)
in ``docs/music-todo.md``.
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field

from src.domain.music import Track
from src.integrations.media_extractor import MediaExtractor


@dataclass
class GuildMusicPlayer:
    """All mutable music state belonging to one Discord guild."""

    guild_id: int
    queue: deque[Track] = field(default_factory=deque)
    current: Track | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # TODO(MUSIC-3): Add enqueue and queue snapshot methods.
    # TODO(MUSIC-4): Store or receive the guild VoiceClient.
    # TODO(MUSIC-5): Add a playback worker and next-track signal.
    # TODO(MUSIC-8): Add an idle-disconnect task.


class MusicService:
    """Coordinate players without depending on slash-command responses."""

    def __init__(self, extractor: MediaExtractor):
        self.extractor = extractor
        self._players: dict[int, GuildMusicPlayer] = {}

    def get_player(self, guild_id: int) -> GuildMusicPlayer:
        # TODO(MUSIC-3): Return one persistent player per guild.
        raise NotImplementedError("TODO(MUSIC-3): create per-guild players")

    async def enqueue(self, guild_id: int, query: str, requested_by: int) -> Track:
        # TODO(MUSIC-3): Search through the extractor and append to the queue.
        raise NotImplementedError("TODO(MUSIC-3): enqueue a track")

    # TODO(MUSIC-5): Implement play_next, pause, resume, skip, stop, and leave.
