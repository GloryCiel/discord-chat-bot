"""Conversation history and AI response handling."""

import asyncio
import logging
from typing import Protocol

from src.config.settings import AiSettings
from src.integrations.groq_client import GroqChatClient


class ChatCompletionClient(Protocol):
    async def complete(self, messages: list[dict[str, str]]) -> str: ...


class ChatHandler:
    def __init__(
        self,
        settings: AiSettings,
        client: ChatCompletionClient | None = None,
    ):
        """Initialize one isolated conversation."""
        self.client = client if client is not None else GroqChatClient(settings)
        self.system_prompt = settings.system_prompt
        self.history: list[dict[str, str]] = []
        self.max_history_messages = 20
        self.logger = logging.getLogger(__name__)
        self._lock = asyncio.Lock()

    async def process_message(self, message: str) -> str:
        async with self._lock:
            try:
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    *self.history,
                    {"role": "user", "content": message},
                ]
                response = await self.client.complete(messages)
                self.history.extend(
                    [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": response},
                    ]
                )
                self.history = self.history[-self.max_history_messages :]
                return response
            except Exception:
                self.logger.exception("AI response generation failed")
                return "AI 응답을 만드는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

    async def reset_chat(self) -> None:
        async with self._lock:
            self.history.clear()

    def get_chat_history(self) -> list[dict[str, str]]:
        return list(self.history)
