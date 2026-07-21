"""Environment-backed application settings."""

from dataclasses import dataclass
import os
from typing import Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class DiscordSettings:
    token: str
    control_guild_id: Optional[int]
    control_user_ids: frozenset[int]
    control_role_ids: frozenset[int]


@dataclass(frozen=True)
class AiSettings:
    groq_api_key: Optional[str]
    model: str
    system_prompt: str

    @property
    def enabled(self) -> bool:
        return bool(self.groq_api_key)


@dataclass(frozen=True)
class GcpSettings:
    project_id: str
    zone: str
    instance_name: str
    service_account_json_base64: Optional[str]
    application_credentials: Optional[str]
    game_metadata_key: str = "active-game"
    palworld_port: int = 8211
    rust_port: int = 28015

    @property
    def enabled(self) -> bool:
        return all((self.project_id, self.zone, self.instance_name))


class Settings:
    """Load and validate all application settings from the environment."""

    def __init__(self) -> None:
        load_dotenv()

        self.discord = DiscordSettings(
            token=os.getenv("DISCORD_TOKEN", ""),
            control_guild_id=self._optional_int(os.getenv("DISCORD_CONTROL_GUILD_ID")),
            control_user_ids=self._int_set(os.getenv("DISCORD_CONTROL_USER_IDS", "")),
            control_role_ids=self._int_set(os.getenv("DISCORD_CONTROL_ROLE_IDS", "")),
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
        self.gcp = GcpSettings(
            project_id=os.getenv("GCP_PROJECT_ID", ""),
            zone=os.getenv("GCP_ZONE", ""),
            instance_name=os.getenv("GCP_INSTANCE_NAME", ""),
            service_account_json_base64=os.getenv("GCP_SERVICE_ACCOUNT_JSON_BASE64"),
            application_credentials=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            game_metadata_key=os.getenv("GCP_GAME_METADATA_KEY", "active-game"),
            palworld_port=self._int(os.getenv("PALWORLD_PORT", "8211")),
            rust_port=self._int(os.getenv("RUST_PORT", "28015")),
        )

    @staticmethod
    def _optional_int(value: Optional[str]) -> Optional[int]:
        if not value:
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"Expected an integer ID, got: {value}") from exc

    @staticmethod
    def _int(value: str) -> int:
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"Expected an integer, got: {value}") from exc

    @staticmethod
    def _int_set(value: str) -> frozenset[int]:
        try:
            return frozenset(
                int(item.strip()) for item in value.split(",") if item.strip()
            )
        except ValueError as exc:
            raise ValueError(
                "Discord ID lists must contain comma-separated integers"
            ) from exc

    def validate(self) -> None:
        if not self.discord.token:
            raise ValueError("Discord token is required")
