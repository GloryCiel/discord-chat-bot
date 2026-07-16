"""
Configuration settings management
"""
import os
from dotenv import load_dotenv
from typing import Optional

class Settings:
    def __init__(self):
        """Load environment variables and initialize settings"""
        load_dotenv()
        
        # Discord settings
        self.discord_token: str = os.getenv("DISCORD_TOKEN", "")
        
        # AI settings (Groq free tier)
        self.groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY")
        self.groq_model: str = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")
        self.ai_system_prompt: str = os.getenv(
            "AI_SYSTEM_PROMPT",
            "You are a friendly Discord chatbot. Reply naturally in the user's language. "
            "Keep answers concise unless the user asks for detail.",
        )
        self.ai_enabled: bool = bool(self.groq_api_key)

        # Palworld GCP instance control
        self.gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "")
        self.gcp_zone: str = os.getenv("GCP_ZONE", "")
        self.gcp_instance_name: str = os.getenv("GCP_INSTANCE_NAME", "")
        self.gcp_service_account_json_base64: Optional[str] = os.getenv(
            "GCP_SERVICE_ACCOUNT_JSON_BASE64"
        )
        self.google_application_credentials: Optional[str] = os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        self.discord_control_guild_id: Optional[int] = self._optional_int(
            os.getenv("DISCORD_CONTROL_GUILD_ID")
        )
        self.discord_control_user_ids = self._int_set(
            os.getenv("DISCORD_CONTROL_USER_IDS", "")
        )
        self.discord_control_role_ids = self._int_set(
            os.getenv("DISCORD_CONTROL_ROLE_IDS", "")
        )
        self.server_control_enabled = all([
            self.gcp_project_id,
            self.gcp_zone,
            self.gcp_instance_name,
            self.discord_control_guild_id,
        ])

    @staticmethod
    def _optional_int(value: Optional[str]) -> Optional[int]:
        if not value:
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"Expected an integer ID, got: {value}") from exc

    @staticmethod
    def _int_set(value: str) -> set[int]:
        try:
            return {int(item.strip()) for item in value.split(",") if item.strip()}
        except ValueError as exc:
            raise ValueError("Discord ID lists must contain comma-separated integers") from exc
        
    def validate(self) -> bool:
        """
        Validate required settings are present
        
        Returns:
            bool: True if all required settings are valid
        """
        if not self.discord_token:
            raise ValueError("Discord token is required")
        return True 
