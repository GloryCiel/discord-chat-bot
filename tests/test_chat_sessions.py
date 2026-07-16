import unittest

from src.config.settings import AiSettings
from src.services.chat_sessions import ChatSessionKey, ChatSessionManager


class ChatSessionManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        settings = AiSettings(
            groq_api_key="test-key",
            model="test-model",
            system_prompt="test-prompt",
        )
        self.manager = ChatSessionManager(settings)
        self.first = ChatSessionKey(1, 10, 100)
        self.second = ChatSessionKey(1, 10, 200)

    async def test_sessions_are_isolated_by_user(self) -> None:
        self.manager.start(self.first)

        self.assertTrue(self.manager.is_active(self.first))
        self.assertFalse(self.manager.is_active(self.second))
        self.assertIsNot(
            self.manager.get_handler(self.first),
            self.manager.get_handler(self.second),
        )

    async def test_stopping_one_session_does_not_stop_another(self) -> None:
        self.manager.start(self.first)
        self.manager.start(self.second)

        stopped = await self.manager.stop(self.first)

        self.assertTrue(stopped)
        self.assertFalse(self.manager.is_active(self.first))
        self.assertTrue(self.manager.is_active(self.second))
