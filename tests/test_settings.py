import os
import unittest
from unittest.mock import patch

from src.config.settings import Settings


class SettingsTests(unittest.TestCase):
    @patch("src.config.settings.load_dotenv")
    def test_parses_feature_settings(self, load_dotenv_mock) -> None:
        environment = {
            "DISCORD_TOKEN": "discord-token",
            "GROQ_API_KEY": "groq-key",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings()

        load_dotenv_mock.assert_called_once_with()
        self.assertEqual(settings.discord.token, "discord-token")
        self.assertTrue(settings.ai.enabled)

    @patch("src.config.settings.load_dotenv")
    def test_requires_discord_token(self, load_dotenv_mock) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

        with self.assertRaisesRegex(ValueError, "Discord token is required"):
            settings.validate()
