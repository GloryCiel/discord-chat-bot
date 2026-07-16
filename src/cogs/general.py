"""General Discord commands."""

import discord
from discord import app_commands
from discord.ext import commands


class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="사용 가능한 명령어를 표시합니다")
    async def help_command(self, interaction: discord.Interaction) -> None:
        available = sorted(
            self.bot.tree.get_commands(), key=lambda command: command.name
        )
        lines = ["**사용 가능한 명령어:**"]
        lines.extend(
            f"`/{command.qualified_name}` - {command.description}"
            for command in available
        )
        await interaction.response.send_message("\n".join(lines))
