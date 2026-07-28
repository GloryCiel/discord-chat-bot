"""Environment-backed application settings."""

from dataclasses import dataclass
import os
from typing import Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class DiscordSettings:
    token: str


@dataclass(frozen=True)
class AiSettings:
    groq_api_key: Optional[str]
    model: str
    system_prompt: str

    @property
    def enabled(self) -> bool:
        return bool(self.groq_api_key)


class Settings:
    """Load and validate all application settings from the environment."""

    def __init__(self) -> None:
        load_dotenv()

        self.discord = DiscordSettings(
            token=os.getenv("DISCORD_TOKEN", ""),
        )
        self.ai = AiSettings(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model=os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b"),
            system_prompt=os.getenv(
                "AI_SYSTEM_PROMPT",
                "You are a friendly Discord chatbot. Reply naturally in the "
                "user's language. Keep answers concise unless the user asks "
                "for detail.",
            ),
        )
    def validate(self) -> None:
        if not self.discord.token:
            raise ValueError("Discord token is required")
