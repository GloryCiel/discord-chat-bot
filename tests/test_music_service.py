import asyncio
import unittest

from src.domain.music import Track
from src.services.music import MusicQueueFullError, MusicService


class FakeMediaExtractor:
    async def search(self, query: str, requested_by: int) -> Track:
        return Track(
            title=query,
            webpage_url=f"https://example.com/{query}",
            requested_by=requested_by,
            duration_seconds=60,
        )

    async def get_stream_url(self, track: Track) -> str:
        return f"https://media.example.com/{track.title}"


class MusicServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.service = MusicService(FakeMediaExtractor(), max_queue_size=2)

    def test_returns_one_persistent_player_per_guild(self) -> None:
        first = self.service.get_player(1)
        same = self.service.get_player(1)
        other = self.service.get_player(2)

        self.assertIs(first, same)
        self.assertIsNot(first, other)

    async def test_guild_queues_are_isolated_and_fifo(self) -> None:
        await self.service.enqueue(1, "first", 100)
        await self.service.enqueue(1, "second", 100)
        await self.service.enqueue(2, "other", 200)

        first_guild = await self.service.queue_snapshot(1)
        second_guild = await self.service.queue_snapshot(2)

        self.assertEqual(
            [track.title for track in first_guild.queued],
            ["first", "second"],
        )
        self.assertEqual(
            [track.title for track in second_guild.queued],
            ["other"],
        )

    async def test_duplicate_tracks_are_allowed(self) -> None:
        first = await self.service.enqueue(1, "same", 100)
        second = await self.service.enqueue(1, "same", 100)

        self.assertEqual(first.position, 1)
        self.assertEqual(second.position, 2)

    async def test_rejects_tracks_over_queue_limit(self) -> None:
        await self.service.enqueue(1, "first", 100)
        await self.service.enqueue(1, "second", 100)

        with self.assertRaisesRegex(MusicQueueFullError, "최대 2곡"):
            await self.service.enqueue(1, "third", 100)

    async def test_concurrent_enqueues_do_not_exceed_limit(self) -> None:
        results = await asyncio.gather(
            self.service.enqueue(1, "first", 100),
            self.service.enqueue(1, "second", 100),
            self.service.enqueue(1, "third", 100),
            return_exceptions=True,
        )
        snapshot = await self.service.queue_snapshot(1)

        self.assertEqual(len(snapshot.queued), 2)
        self.assertEqual(
            sum(isinstance(result, MusicQueueFullError) for result in results),
            1,
        )

    def test_rejects_invalid_queue_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 1"):
            MusicService(FakeMediaExtractor(), max_queue_size=0)
