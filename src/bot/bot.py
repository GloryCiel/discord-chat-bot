"""
Main Discord bot class implementation
"""
import discord
from discord import app_commands
from typing import Optional, Dict
from src.ai.chat_handler import ChatHandler
from src.config.settings import Settings

class DiscordBot(discord.Client):
    def __init__(self, settings: Settings, intents: Optional[discord.Intents] = None):
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.members = True
        
        super().__init__(intents=intents)
        self.settings = settings
        self.chat_handlers: Dict[int, ChatHandler] = {}  # channel_id -> ChatHandler
        self.tree = app_commands.CommandTree(self)
        
    async def setup_hook(self) -> None:
        """Initialize bot commands and other setup tasks"""
        # Add commands here
        @self.tree.command(name="chat", description="Start a new chat session")
        async def chat(interaction: discord.Interaction):
            channel_id = interaction.channel_id
            if channel_id in self.chat_handlers:
                await self.chat_handlers[channel_id].reset_chat()
            await interaction.response.send_message("새로운 채팅 세션이 시작되었습니다!")
            
        @self.tree.command(name="help", description="Show available commands")
        async def help(interaction: discord.Interaction):
            help_text = """
            **사용 가능한 명령어:**
            `/chat` - 새로운 채팅 세션 시작
            `/help` - 도움말 표시
            
            **일반 채팅:**
            명령어 없이 메시지를 보내면 AI와 대화할 수 있습니다.
            """
            await interaction.response.send_message(help_text)
            
        # Sync commands with Discord
        await self.tree.sync()
        
    async def on_ready(self) -> None:
        """Called when the bot is ready and connected to Discord"""
        print(f"Logged in as {self.user.name} (ID: {self.user.id})")
        print("------")
        
    async def get_chat_handler(self, channel_id: int) -> ChatHandler:
        """
        Get or create a chat handler for a channel
        
        Args:
            channel_id (int): Discord channel ID
            
        Returns:
            ChatHandler: Chat handler instance for the channel
        """
        if channel_id not in self.chat_handlers:
            self.chat_handlers[channel_id] = ChatHandler(self.settings)
        return self.chat_handlers[channel_id]
        
    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming messages"""
        # Ignore messages from the bot itself
        if message.author == self.user:
            return
            
        # Ignore messages that start with / (slash commands)
        if message.content.startswith('/'):
            return
            
        # Get chat handler for this channel
        chat_handler = await self.get_chat_handler(message.channel.id)
        
        # Generate and send response
        async with message.channel.typing():
            response = await chat_handler.process_message(message.content)
            await message.reply(response) 
