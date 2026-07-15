"""AI chat handling implementation using Groq's OpenAI-compatible API."""
from typing import Dict, Any, List

from groq import AsyncGroq

from src.config.settings import Settings

class ChatHandler:
    def __init__(self, settings: Settings):
        """Initialize a channel-local chat session."""
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required to use AI chat")

        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
        self.system_prompt = settings.ai_system_prompt
        self.history: List[Dict[str, str]] = []
        self.max_history_messages = 20
        
    async def process_message(self, message: str) -> str:
        """
        Process a user message and generate an AI response.
        
        Args:
            message (str): User's message
            
        Returns:
            str: AI generated response
        """
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                *self.history,
                {"role": "user", "content": message},
            ]
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
                reasoning_format="hidden",
            )
            response = completion.choices[0].message.content or "응답이 비어 있습니다."
            self.history.extend([
                {"role": "user", "content": message},
                {"role": "assistant", "content": response},
            ])
            self.history = self.history[-self.max_history_messages:]
            return response
        except Exception as e:
            print(f"Groq API error: {e}")
            return "AI 응답을 만드는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        
    async def reset_chat(self) -> None:
        """Reset the chat history"""
        self.history.clear()
        
    async def get_chat_history(self) -> List[Dict[str, str]]:
        """
        Get the current chat history
        
        Returns:
            List[Dict[str, str]]: List of chat messages with roles and content
        """
        return list(self.history)

    async def train(self, training_data: Dict[str, Any]) -> None:
        """
        Train or fine-tune the AI model
        
        Args:
            training_data (Dict[str, Any]): Training data for the model
        """
        # Training logic will be implemented here
        pass 
