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
        
    def validate(self) -> bool:
        """
        Validate required settings are present
        
        Returns:
            bool: True if all required settings are valid
        """
        if not self.discord_token:
            raise ValueError("Discord token is required")
        return True 
