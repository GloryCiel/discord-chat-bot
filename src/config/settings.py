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
        
        # Gemini API settings
        self.gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        
    def validate(self) -> bool:
        """
        Validate required settings are present
        
        Returns:
            bool: True if all required settings are valid
        """
        if not self.discord_token:
            raise ValueError("Discord token is required")
        if not self.gemini_api_key:
            raise ValueError("Gemini API key is required")
        return True 
