import asyncio
import unittest

from src.ai.chat_handler import ChatHandler
from src.config.settings import AiSettings


class FakeChatClient:
    def __init__(self):
        self.requests: list[list[dict[str, str]]] = []

    async def complete(self, messages: list[dict[str, str]]) -> str:
        self.requests.append(messages)
        return "assistant-response"


class ConcurrentChatClient:
    def __init__(self):
        self.active_requests = 0
        self.max_active_requests = 0

    async def complete(self, messages: list[dict[str, str]]) -> str:
        self.active_requests += 1
        self.max_active_requests = max(self.max_active_requests, self.active_requests)
        await asyncio.sleep(0.01)
        self.active_requests -= 1
        return f"reply-{messages[-1]['content']}"


class ChatHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_response_is_added_to_history(self) -> None:
        settings = AiSettings(None, "test-model", "system-prompt")
        client = FakeChatClient()
        handler = ChatHandler(settings, client)

        response = await handler.process_message("hello")

        self.assertEqual(response, "assistant-response")
        self.assertEqual(
            handler.get_chat_history(),
            [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "assistant-response"},
            ],
        )
        self.assertEqual(client.requests[0][0]["role"], "system")

    async def test_concurrent_messages_are_processed_in_order(self) -> None:
        settings = AiSettings(None, "test-model", "system-prompt")
        client = ConcurrentChatClient()
        handler = ChatHandler(settings, client)

        await asyncio.gather(
            handler.process_message("first"),
            handler.process_message("second"),
        )

        self.assertEqual(client.max_active_requests, 1)
        self.assertEqual(
            [item["content"] for item in handler.get_chat_history()],
            ["first", "reply-first", "second", "reply-second"],
        )
