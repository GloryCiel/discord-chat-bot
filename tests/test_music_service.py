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


class FakeVoiceClient:
    def __init__(
        self,
        channel: "FakeVoiceChannel",
        connected: bool = True,
        auto_finish: bool = True,
    ):
        self.channel = channel
        self.connected = connected
        self.auto_finish = auto_finish
        self.playing = False
        self.paused = False
        self.disconnected = False
        self.moves: list[FakeVoiceChannel] = []
        self.sources: list[FakeAudioSource] = []
        self.after_callbacks = []

    def is_connected(self) -> bool:
        return self.connected

    async def move_to(self, channel: "FakeVoiceChannel") -> None:
        self.channel = channel
        self.moves.append(channel)

    def play(self, source: "FakeAudioSource", *, after=None) -> None:
        self.playing = True
        self.paused = False
        self.sources.append(source)
        self.after_callbacks.append(after)
        if self.auto_finish:
            asyncio.get_running_loop().call_soon(self.finish)

    def finish(self, error: Exception | None = None) -> None:
        self.playing = False
        self.paused = False
        callback = self.after_callbacks[-1]
        if callback is not None:
            callback(error)

    def is_playing(self) -> bool:
        return self.playing

    def is_paused(self) -> bool:
        return self.paused

    def pause(self) -> None:
        self.playing = False
        self.paused = True

    def resume(self) -> None:
        self.playing = True
        self.paused = False

    def stop(self) -> None:
        if self.playing or self.paused:
            self.finish()

    async def disconnect(self, *, force: bool = False) -> None:
        self.connected = False
        self.disconnected = True


class FakeAudioSource:
    def __init__(self, stream_url: str):
        self.stream_url = stream_url
        self.cleaned = False

    def cleanup(self) -> None:
        self.cleaned = True


class FakeVoiceChannel:
    def __init__(self, channel_id: int):
        self.id = channel_id
        self.connect_count = 0
        self.client = FakeVoiceClient(self)

    async def connect(self) -> FakeVoiceClient:
        self.connect_count += 1
        return self.client


class MusicServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.created_sources: list[FakeAudioSource] = []

        def create_source(stream_url: str) -> FakeAudioSource:
            source = FakeAudioSource(stream_url)
            self.created_sources.append(source)
            return source

        self.service = MusicService(
            FakeMediaExtractor(),
            max_queue_size=2,
            audio_source_factory=create_source,
        )

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

    async def test_connects_and_stores_voice_client(self) -> None:
        channel = FakeVoiceChannel(10)

        voice_client = await self.service.connect(1, channel)

        self.assertIs(voice_client, channel.client)
        self.assertIs(self.service.get_player(1).voice_client, channel.client)
        self.assertEqual(channel.connect_count, 1)
        self.assertEqual(await self.service.connected_channel_id(1), 10)

    async def test_reuses_client_in_same_voice_channel(self) -> None:
        channel = FakeVoiceChannel(10)
        await self.service.connect(1, channel)

        voice_client = await self.service.connect(1, channel)

        self.assertIs(voice_client, channel.client)
        self.assertEqual(channel.connect_count, 1)
        self.assertEqual(channel.client.moves, [])

    async def test_moves_existing_client_to_requested_channel(self) -> None:
        first_channel = FakeVoiceChannel(10)
        second_channel = FakeVoiceChannel(20)
        await self.service.connect(1, first_channel)

        voice_client = await self.service.connect(1, second_channel)

        self.assertIs(voice_client, first_channel.client)
        self.assertEqual(first_channel.client.moves, [second_channel])
        self.assertEqual(await self.service.connected_channel_id(1), 20)
        self.assertEqual(second_channel.connect_count, 0)

    async def test_reconnects_when_stored_client_is_stale(self) -> None:
        stale_channel = FakeVoiceChannel(10)
        new_channel = FakeVoiceChannel(20)
        stale_channel.client.connected = False
        self.service.get_player(1).voice_client = stale_channel.client

        voice_client = await self.service.connect(1, new_channel)

        self.assertIs(voice_client, new_channel.client)
        self.assertEqual(new_channel.connect_count, 1)

    async def test_voice_clients_are_isolated_per_guild(self) -> None:
        first_channel = FakeVoiceChannel(10)
        second_channel = FakeVoiceChannel(20)

        await self.service.connect(1, first_channel)
        await self.service.connect(2, second_channel)

        self.assertEqual(await self.service.connected_channel_id(1), 10)
        self.assertEqual(await self.service.connected_channel_id(2), 20)

    async def test_playback_worker_plays_queue_in_fifo_order(self) -> None:
        channel = FakeVoiceChannel(10)
        await self.service.connect(1, channel)
        await self.service.enqueue(1, "first", 100)
        await self.service.enqueue(1, "second", 100)

        started = await self.service.start_playback(1)
        playback_task = self.service.get_player(1).playback_task
        self.assertIsNotNone(playback_task)
        await playback_task

        self.assertTrue(started)
        self.assertEqual(
            [source.stream_url for source in channel.client.sources],
            [
                "https://media.example.com/first",
                "https://media.example.com/second",
            ],
        )
        snapshot = await self.service.queue_snapshot(1)
        self.assertIsNone(snapshot.current)
        self.assertEqual(snapshot.queued, ())
        self.assertIsNone(self.service.get_player(1).playback_task)

    async def test_start_playback_requires_connection_and_queued_track(self) -> None:
        self.assertFalse(await self.service.start_playback(1))

        channel = FakeVoiceChannel(10)
        await self.service.connect(1, channel)

        self.assertFalse(await self.service.start_playback(1))

    async def test_does_not_start_second_worker_for_same_guild(self) -> None:
        channel = FakeVoiceChannel(10)
        channel.client.auto_finish = False
        await self.service.connect(1, channel)
        await self.service.enqueue(1, "first", 100)

        self.assertTrue(await self.service.start_playback(1))
        await asyncio.sleep(0)
        self.assertFalse(await self.service.start_playback(1))

        playback_task = self.service.get_player(1).playback_task
        channel.client.finish()
        self.assertIsNotNone(playback_task)
        await playback_task

    async def test_playback_error_skips_to_next_track(self) -> None:
        class FailingExtractor(FakeMediaExtractor):
            async def get_stream_url(self, track: Track) -> str:
                if track.title == "broken":
                    raise RuntimeError("extraction failed")
                return await super().get_stream_url(track)

        self.service.extractor = FailingExtractor()
        channel = FakeVoiceChannel(10)
        await self.service.connect(1, channel)
        await self.service.enqueue(1, "broken", 100)
        await self.service.enqueue(1, "working", 100)

        with self.assertLogs("src.services.music", level="ERROR"):
            self.assertTrue(await self.service.start_playback(1))
            playback_task = self.service.get_player(1).playback_task
            self.assertIsNotNone(playback_task)
            await playback_task

        self.assertEqual(
            [source.stream_url for source in channel.client.sources],
            ["https://media.example.com/working"],
        )

    async def test_pause_and_resume_active_playback(self) -> None:
        channel = FakeVoiceChannel(10)
        channel.client.auto_finish = False
        await self.service.connect(1, channel)
        await self.service.enqueue(1, "first", 100)
        await self.service.start_playback(1)
        await asyncio.sleep(0)

        self.assertTrue(await self.service.pause(1))
        self.assertTrue(channel.client.is_paused())
        self.assertFalse(await self.service.pause(1))

        self.assertTrue(await self.service.resume(1))
        self.assertTrue(channel.client.is_playing())
        self.assertFalse(await self.service.resume(1))

        await self.service.stop(1)

    async def test_skip_advances_to_next_track(self) -> None:
        channel = FakeVoiceChannel(10)
        channel.client.auto_finish = False
        await self.service.connect(1, channel)
        await self.service.enqueue(1, "first", 100)
        await self.service.enqueue(1, "second", 100)
        await self.service.start_playback(1)
        await asyncio.sleep(0)

        skipped = await self.service.skip(1)
        await asyncio.sleep(0)

        self.assertIsNotNone(skipped)
        self.assertEqual(skipped.title, "first")
        self.assertEqual(
            [source.stream_url for source in channel.client.sources],
            [
                "https://media.example.com/first",
                "https://media.example.com/second",
            ],
        )
        snapshot = await self.service.queue_snapshot(1)
        self.assertIsNotNone(snapshot.current)
        self.assertEqual(snapshot.current.title, "second")
        await self.service.stop(1)

    async def test_stop_clears_queue_and_keeps_connection(self) -> None:
        channel = FakeVoiceChannel(10)
        channel.client.auto_finish = False
        await self.service.connect(1, channel)
        await self.service.enqueue(1, "first", 100)
        await self.service.enqueue(1, "second", 100)
        await self.service.start_playback(1)
        await asyncio.sleep(0)

        self.assertTrue(await self.service.stop(1))

        snapshot = await self.service.queue_snapshot(1)
        self.assertIsNone(snapshot.current)
        self.assertEqual(snapshot.queued, ())
        self.assertTrue(channel.client.is_connected())
        self.assertIsNone(self.service.get_player(1).playback_task)
        self.assertFalse(await self.service.stop(1))

    async def test_leave_stops_and_disconnects(self) -> None:
        channel = FakeVoiceChannel(10)
        channel.client.auto_finish = False
        await self.service.connect(1, channel)
        await self.service.enqueue(1, "first", 100)
        await self.service.start_playback(1)
        await asyncio.sleep(0)

        self.assertTrue(await self.service.leave(1))

        self.assertTrue(channel.client.disconnected)
        self.assertIsNone(self.service.get_player(1).voice_client)
        self.assertIsNone(await self.service.connected_channel_id(1))
        self.assertFalse(await self.service.leave(1))
