"""Discord slash commands for music playback.

This Cog is intentionally not loaded by ``DiscordBot`` yet. Complete
TODO(MUSIC-1) through TODO(MUSIC-6), then load it in TODO(MUSIC-7).
"""

import discord
from discord import app_commands
from discord.ext import commands

from src.services.music import MusicService


class MusicCog(commands.Cog):
    def __init__(self, service: MusicService):
        self.service = service

    async def _not_ready(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "음악 기능을 구현하는 중입니다.", ephemeral=True
        )

    @app_commands.command(
        name="music_play", description="음악을 검색하거나 큐에 추가합니다"
    )
    @app_commands.describe(query="곡 검색어 또는 지원되는 미디어 URL")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        # TODO(MUSIC-4): Validate the user's voice channel and connect the bot.
        # TODO(MUSIC-6): Defer, enqueue, and display the Track metadata.
        await self._not_ready(interaction)

    @app_commands.command(name="music_pause", description="현재 음악을 일시정지합니다")
    async def pause(self, interaction: discord.Interaction) -> None:
        # TODO(MUSIC-6): Pause only when the guild is currently playing.
        await self._not_ready(interaction)

    @app_commands.command(
        name="music_resume", description="일시정지한 음악을 다시 재생합니다"
    )
    async def resume(self, interaction: discord.Interaction) -> None:
        # TODO(MUSIC-6): Resume only when the guild is paused.
        await self._not_ready(interaction)

    @app_commands.command(name="music_skip", description="현재 음악을 건너뜁니다")
    async def skip(self, interaction: discord.Interaction) -> None:
        # TODO(MUSIC-6): Stop the current source and advance the queue once.
        await self._not_ready(interaction)

    @app_commands.command(
        name="music_queue", description="현재 음악 대기열을 표시합니다"
    )
    async def show_queue(self, interaction: discord.Interaction) -> None:
        # TODO(MUSIC-6): Show current Track and a bounded queue preview.
        await self._not_ready(interaction)

    @app_commands.command(
        name="music_stop", description="재생을 중단하고 대기열을 비웁니다"
    )
    async def stop(self, interaction: discord.Interaction) -> None:
        # TODO(MUSIC-6): Stop playback but keep the voice connection.
        await self._not_ready(interaction)

    @app_commands.command(
        name="music_leave", description="재생을 중단하고 음성 채널에서 나갑니다"
    )
    async def leave(self, interaction: discord.Interaction) -> None:
        # TODO(MUSIC-6): Clear the guild player and disconnect VoiceClient.
        await self._not_ready(interaction)
