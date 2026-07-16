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

    async def _user_voice_channel(
        self, interaction: discord.Interaction
    ) -> discord.VoiceChannel | None:
        if interaction.guild is None or not isinstance(
            interaction.user, discord.Member
        ):
            await interaction.response.send_message(
                "서버 안에서만 사용할 수 있는 명령어입니다.", ephemeral=True
            )
            return None

        voice_state = interaction.user.voice
        if voice_state is None or voice_state.channel is None:
            await interaction.response.send_message(
                "먼저 음성 채널에 입장해 주세요.", ephemeral=True
            )
            return None

        if not isinstance(voice_state.channel, discord.VoiceChannel):
            await interaction.response.send_message(
                "현재는 일반 음성 채널에서만 사용할 수 있습니다.", ephemeral=True
            )
            return None
        return voice_state.channel

    async def _require_same_voice_channel(
        self, interaction: discord.Interaction
    ) -> bool:
        channel = await self._user_voice_channel(interaction)
        if channel is None or interaction.guild is None:
            return False

        connected_channel_id = await self.service.connected_channel_id(
            interaction.guild.id
        )
        if connected_channel_id is None:
            await interaction.response.send_message(
                "봇이 음성 채널에 연결되어 있지 않습니다.", ephemeral=True
            )
            return False
        if connected_channel_id != channel.id:
            await interaction.response.send_message(
                "봇과 같은 음성 채널에서만 제어할 수 있습니다.",
                ephemeral=True,
            )
            return False
        return True

    @app_commands.command(
        name="music_play", description="음악을 검색하거나 큐에 추가합니다"
    )
    @app_commands.describe(query="곡 검색어 또는 지원되는 미디어 URL")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        channel = await self._user_voice_channel(interaction)
        if channel is None or interaction.guild is None:
            return

        bot_member = interaction.guild.me
        if bot_member is None:
            await interaction.response.send_message(
                "봇의 서버 정보를 확인할 수 없습니다.", ephemeral=True
            )
            return

        permissions = channel.permissions_for(bot_member)
        missing_permissions = [
            label
            for allowed, label in (
                (permissions.view_channel, "채널 보기"),
                (permissions.connect, "연결"),
                (permissions.speak, "말하기"),
            )
            if not allowed
        ]
        if missing_permissions:
            await interaction.response.send_message(
                "봇에 필요한 음성 채널 권한이 없습니다: "
                + ", ".join(missing_permissions),
                ephemeral=True,
            )
            return

        await self.service.connect(interaction.guild.id, channel)
        # TODO(MUSIC-6): Defer, enqueue, and display the Track metadata.
        await self._not_ready(interaction)

    @app_commands.command(name="music_pause", description="현재 음악을 일시정지합니다")
    async def pause(self, interaction: discord.Interaction) -> None:
        # TODO(MUSIC-6): Pause only when the guild is currently playing.
        if await self._require_same_voice_channel(interaction):
            await self._not_ready(interaction)

    @app_commands.command(
        name="music_resume", description="일시정지한 음악을 다시 재생합니다"
    )
    async def resume(self, interaction: discord.Interaction) -> None:
        # TODO(MUSIC-6): Resume only when the guild is paused.
        if await self._require_same_voice_channel(interaction):
            await self._not_ready(interaction)

    @app_commands.command(name="music_skip", description="현재 음악을 건너뜁니다")
    async def skip(self, interaction: discord.Interaction) -> None:
        # TODO(MUSIC-6): Stop the current source and advance the queue once.
        if await self._require_same_voice_channel(interaction):
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
        if await self._require_same_voice_channel(interaction):
            await self._not_ready(interaction)

    @app_commands.command(
        name="music_leave", description="재생을 중단하고 음성 채널에서 나갑니다"
    )
    async def leave(self, interaction: discord.Interaction) -> None:
        # TODO(MUSIC-6): Clear the guild player and disconnect VoiceClient.
        if await self._require_same_voice_channel(interaction):
            await self._not_ready(interaction)
