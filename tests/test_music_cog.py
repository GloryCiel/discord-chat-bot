import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.cogs.music import MusicCog
from src.domain.music import Track
from src.services.music import EnqueueResult, QueueSnapshot


def make_track(title: str, duration: int | None = 60) -> Track:
    return Track(
        title=title,
        webpage_url=f"https://example.com/{title}",
        requested_by=100,
        duration_seconds=duration,
    )


class MusicCogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.service = SimpleNamespace(queue_snapshot=AsyncMock())
        self.cog = MusicCog(self.service)
        self.interaction = SimpleNamespace(
            guild=SimpleNamespace(id=1),
            response=SimpleNamespace(send_message=AsyncMock()),
        )

    def test_formats_track_and_escapes_discord_markdown(self) -> None:
        label = self.cog._format_track(make_track("an *important* song", 185))

        self.assertEqual(label, "**an \\*important\\* song** (`3:05`)")

    async def test_queue_command_shows_current_and_limits_preview(self) -> None:
        self.service.queue_snapshot.return_value = QueueSnapshot(
            current=make_track("current"),
            queued=tuple(make_track(f"track-{index}") for index in range(12)),
        )

        await MusicCog.show_queue.callback(self.cog, self.interaction)

        self.service.queue_snapshot.assert_awaited_once_with(1)
        message = self.interaction.response.send_message.await_args.args[0]
        self.assertIn("지금 재생: **current**", message)
        self.assertIn("10. **track-9**", message)
        self.assertNotIn("track-10", message)
        self.assertIn("…외 2곡", message)

    async def test_queue_command_reports_empty_queue(self) -> None:
        self.service.queue_snapshot.return_value = QueueSnapshot(
            current=None,
            queued=(),
        )

        await MusicCog.show_queue.callback(self.cog, self.interaction)

        self.interaction.response.send_message.assert_awaited_once_with(
            "음악 대기열이 비어 있습니다."
        )

    async def test_queue_command_rejects_direct_message(self) -> None:
        self.interaction.guild = None

        await MusicCog.show_queue.callback(self.cog, self.interaction)

        self.service.queue_snapshot.assert_not_awaited()
        self.interaction.response.send_message.assert_awaited_once_with(
            "서버 안에서만 사용할 수 있는 명령어입니다.", ephemeral=True
        )

    async def test_play_connects_enqueues_and_starts_playback(self) -> None:
        class FakeVoiceChannel:
            id = 10

            @staticmethod
            def permissions_for(member):
                return SimpleNamespace(
                    view_channel=True,
                    connect=True,
                    speak=True,
                )

        class FakeMember:
            id = 100
            voice = SimpleNamespace(channel=FakeVoiceChannel())

        track = make_track("requested song", 185)
        self.service.connect = AsyncMock()
        self.service.enqueue = AsyncMock(return_value=EnqueueResult(track, 1))
        self.service.start_playback = AsyncMock(return_value=True)
        self.interaction.user = FakeMember()
        self.interaction.guild.me = object()
        self.interaction.response.defer = AsyncMock()
        self.interaction.followup = SimpleNamespace(send=AsyncMock())

        with (
            patch("src.cogs.music.discord.Member", FakeMember),
            patch("src.cogs.music.discord.VoiceChannel", FakeVoiceChannel),
        ):
            await MusicCog.play.callback(self.cog, self.interaction, "song query")

        self.interaction.response.defer.assert_awaited_once_with(thinking=True)
        self.service.connect.assert_awaited_once_with(
            1, self.interaction.user.voice.channel
        )
        self.service.enqueue.assert_awaited_once_with(1, "song query", 100)
        self.service.start_playback.assert_awaited_once_with(1)
        message = self.interaction.followup.send.await_args.args[0]
        self.assertIn("재생을 시작합니다", message)
        self.assertIn("requested song", message)

    async def test_last_human_leaving_schedules_disconnect(self) -> None:
        class FakeVoiceChannel:
            id = 10
            members = [SimpleNamespace(bot=True)]

        guild = SimpleNamespace(
            id=1,
            get_channel=lambda channel_id: FakeVoiceChannel(),
        )
        member = SimpleNamespace(bot=False, guild=guild)
        before = SimpleNamespace(channel=SimpleNamespace(id=10))
        after = SimpleNamespace(channel=None)
        self.service.connected_channel_id = AsyncMock(return_value=10)
        self.service.schedule_idle_disconnect = AsyncMock()

        with patch("src.cogs.music.discord.VoiceChannel", FakeVoiceChannel):
            await self.cog.on_voice_state_update(member, before, after)

        self.service.schedule_idle_disconnect.assert_awaited_once_with(
            1,
            stop_playback=True,
        )

    async def test_human_joining_cancels_disconnect(self) -> None:
        human = SimpleNamespace(bot=False)

        class FakeVoiceChannel:
            id = 10
            members = [SimpleNamespace(bot=True), human]

        guild = SimpleNamespace(
            id=1,
            get_channel=lambda channel_id: FakeVoiceChannel(),
        )
        member = SimpleNamespace(bot=False, guild=guild)
        before = SimpleNamespace(channel=None)
        after = SimpleNamespace(channel=SimpleNamespace(id=10))
        self.service.connected_channel_id = AsyncMock(return_value=10)
        self.service.cancel_idle_disconnect = AsyncMock()

        with patch("src.cogs.music.discord.VoiceChannel", FakeVoiceChannel):
            await self.cog.on_voice_state_update(member, before, after)

        self.service.cancel_idle_disconnect.assert_awaited_once_with(1)
