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
            "GCP_PROJECT_ID": "project-id",
            "GCP_ZONE": "zone-a",
            "GCP_INSTANCE_NAME": "palworld-vm",
            "GCP_GAME_METADATA_KEY": "selected-game",
            "PALWORLD_PORT": "8211",
            "RUST_PORT": "28015",
            "DISCORD_CONTROL_USER_IDS": "1, 2",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = Settings()

        load_dotenv_mock.assert_called_once_with()
        self.assertEqual(settings.discord.token, "discord-token")
        self.assertEqual(settings.discord.control_user_ids, frozenset({1, 2}))
        self.assertTrue(settings.ai.enabled)
        self.assertTrue(settings.gcp.enabled)
        self.assertEqual(settings.gcp.game_metadata_key, "selected-game")
        self.assertEqual(settings.gcp.palworld_port, 8211)
        self.assertEqual(settings.gcp.rust_port, 28015)

    @patch("src.config.settings.load_dotenv")
    def test_requires_discord_token(self, load_dotenv_mock) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

        with self.assertRaisesRegex(ValueError, "Discord token is required"):
            settings.validate()
