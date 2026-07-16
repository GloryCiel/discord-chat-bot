"""Groq API adapter."""

from groq import AsyncGroq

from src.config.settings import AiSettings


class GroqChatClient:
    def __init__(self, settings: AiSettings):
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required to use AI chat")
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.model

    async def complete(self, messages: list[dict[str, str]]) -> str:
        completion = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
            reasoning_format="hidden",
        )
        return completion.choices[0].message.content or "응답이 비어 있습니다."
