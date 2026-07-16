"""User-scoped AI chat session management."""

from dataclasses import dataclass

from src.ai.chat_handler import ChatHandler
from src.config.settings import AiSettings


@dataclass(frozen=True)
class ChatSessionKey:
    guild_id: int
    channel_id: int
    user_id: int


class ChatSessionManager:
    def __init__(self, settings: AiSettings):
        self.settings = settings
        self._active: set[ChatSessionKey] = set()
        self._handlers: dict[ChatSessionKey, ChatHandler] = {}

    def start(self, key: ChatSessionKey) -> None:
        self._active.add(key)

    async def stop(self, key: ChatSessionKey) -> bool:
        if key not in self._active:
            return False
        self._active.remove(key)
        handler = self._handlers.pop(key, None)
        if handler:
            await handler.reset_chat()
        return True

    def is_active(self, key: ChatSessionKey) -> bool:
        return key in self._active

    def get_handler(self, key: ChatSessionKey) -> ChatHandler:
        if key not in self._handlers:
            self._handlers[key] = ChatHandler(self.settings)
        return self._handlers[key]
