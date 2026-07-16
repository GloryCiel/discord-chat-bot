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
                "pal_server_start",
                "pal_server_status",
                "pal_server_stop",
            },
        )
        await bot.close()
