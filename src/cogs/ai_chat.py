"""AI chat commands and message listener."""

import discord
from discord import app_commands
from discord.ext import commands

from src.config.settings import AiSettings
from src.services.chat_sessions import ChatSessionKey, ChatSessionManager
from src.utils.discord_messages import split_message


class AiChatCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        settings: AiSettings,
        sessions: ChatSessionManager,
    ):
        self.bot = bot
        self.settings = settings
        self.sessions = sessions

    @staticmethod
    def _key(guild_id: int | None, channel_id: int, user_id: int) -> ChatSessionKey:
        return ChatSessionKey(guild_id or 0, channel_id, user_id)

    @app_commands.command(name="chat", description="AI와의 대화를 시작합니다")
    async def chat(self, interaction: discord.Interaction) -> None:
        if not self.settings.enabled:
            await interaction.response.send_message(
                "AI 채팅이 비활성화되어 있습니다. 관리자에게 GROQ_API_KEY 설정을 요청하세요.",
                ephemeral=True,
            )
            return
        key = self._key(
            interaction.guild_id, interaction.channel_id, interaction.user.id
        )
        self.sessions.start(key)
        await interaction.response.send_message(
            "이 채널에서 AI와 대화할 수 있습니다. 종료하려면 /end를 입력하세요."
        )

    @app_commands.command(name="end", description="현재 AI 대화를 종료합니다")
    async def end(self, interaction: discord.Interaction) -> None:
        key = self._key(
            interaction.guild_id, interaction.channel_id, interaction.user.id
        )
        if await self.sessions.stop(key):
            message = (
                "AI와의 대화가 종료되었습니다. 다시 시작하려면 /chat을 입력하세요."
            )
        else:
            message = "이 채널에서 활성화된 AI 대화가 없습니다."
        await interaction.response.send_message(message)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.content.startswith("/"):
            return
        key = self._key(
            message.guild.id if message.guild else None,
            message.channel.id,
            message.author.id,
        )
        if not self.sessions.is_active(key):
            return

        handler = self.sessions.get_handler(key)
        async with message.channel.typing():
            response = await handler.process_message(message.content)
            for index, chunk in enumerate(split_message(response)):
                if index == 0:
                    await message.reply(chunk)
                else:
                    await message.channel.send(chunk)
