"""
AI chat handling implementation using Google's Gemini API
"""
import google.generativeai as genai
from typing import Optional, Dict, Any, List
from src.config.settings import Settings

class ChatHandler:
    def __init__(self, settings: Settings):
        """
        Initialize chat handler with Gemini model
        
        Args:
            settings (Settings): Application settings containing API key
        """
        if not settings.gemini_api_key:
            raise ValueError("Gemini API key is required")
            
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self.chat = self.model.start_chat(history=[])
        
    async def process_message(self, message: str) -> str:
        """
        Process user message and generate AI response using Gemini
        
        Args:
            message (str): User's message
            
        Returns:
            str: AI generated response
        """
        try:
            response = await self.chat.send_message_async(message)
            return response.text
        except Exception as e:
            return f"Error generating response: {str(e)}"
        
    async def reset_chat(self) -> None:
        """Reset the chat history"""
        self.chat = self.model.start_chat(history=[])
        
    async def get_chat_history(self) -> List[Dict[str, str]]:
        """
        Get the current chat history
        
        Returns:
            List[Dict[str, str]]: List of chat messages with roles and content
        """
        return [
            {"role": msg.role, "content": msg.parts[0].text}
            for msg in self.chat.history
        ]

    async def train(self, training_data: Dict[str, Any]) -> None:
        """
        Train or fine-tune the AI model
        
        Args:
            training_data (Dict[str, Any]): Training data for the model
        """
        # Training logic will be implemented here
        pass 
