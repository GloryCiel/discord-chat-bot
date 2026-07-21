import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.bot.bot import DiscordBot
from src.config.settings import AiSettings, DiscordSettings, GcpSettings


class BotCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_setup_registers_expected_commands(self) -> None:
        settings = SimpleNamespace(
            ai=AiSettings(None, "test-model", "test-prompt"),
            discord=DiscordSettings("test-token", None, frozenset(), frozenset()),
            gcp=GcpSettings("", "", "", None, None),
        )
        bot = DiscordBot(settings)
        bot.tree.sync = AsyncMock(return_value=[])

        await bot.setup_hook()

        names = {command.name for command in bot.tree.get_commands()}
        self.assertEqual(
            names,
            {
                "chat",
                "end",
                "help",
                "music_leave",
                "music_pause",
                "music_play",
                "music_queue",
                "music_resume",
                "music_skip",
                "music_stop",
                "game_server_start",
                "game_server_status",
                "game_server_stop",
            },
        )

        general_cog = bot.get_cog("GeneralCog")
        self.assertIsNotNone(general_cog)
        interaction = SimpleNamespace(
            response=SimpleNamespace(send_message=AsyncMock())
        )
        await general_cog.help_command.callback(general_cog, interaction)
        help_message = interaction.response.send_message.await_args.args[0]
        self.assertIn("`/music_play`", help_message)
        self.assertIn("`/music_leave`", help_message)
        await bot.close()
