"""Discord slash commands for music playback.

This Cog is intentionally not loaded by ``DiscordBot`` yet. Complete
TODO(MUSIC-1) through TODO(MUSIC-6), then load it in TODO(MUSIC-7).
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from src.domain.music import Track
from src.integrations.media_extractor import MediaExtractionError
from src.services.music import MusicQueueFullError, MusicService

logger = logging.getLogger(__name__)
QUEUE_PREVIEW_LIMIT = 10


class MusicCog(commands.Cog):
    def __init__(self, service: MusicService):
        self.service = service

    @staticmethod
    def _format_track(track: Track) -> str:
        title = discord.utils.escape_markdown(track.title)
        return f"**{title}** (`{track.duration_label}`)"

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

        await interaction.response.defer(thinking=True)
        try:
            await self.service.connect(interaction.guild.id, channel)
            result = await self.service.enqueue(
                interaction.guild.id,
                query,
                interaction.user.id,
            )
            started = await self.service.start_playback(interaction.guild.id)
        except (MediaExtractionError, MusicQueueFullError) as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception:
            logger.exception(
                "Music play command failed in guild %s", interaction.guild.id
            )
            await interaction.followup.send(
                "음악을 준비하지 못했습니다. 잠시 후 다시 시도해 주세요.",
                ephemeral=True,
            )
            return

        track_label = self._format_track(result.track)
        if started:
            message = f"▶️ 재생을 시작합니다: {track_label}"
        else:
            message = f"➕ 대기열 {result.position}번에 추가했습니다: {track_label}"
        await interaction.followup.send(message)

    @app_commands.command(name="music_pause", description="현재 음악을 일시정지합니다")
    async def pause(self, interaction: discord.Interaction) -> None:
        if not await self._require_same_voice_channel(interaction):
            return
        if await self.service.pause(interaction.guild.id):
            message = "⏸️ 음악을 일시정지했습니다."
        else:
            message = "현재 재생 중인 음악이 없습니다."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name="music_resume", description="일시정지한 음악을 다시 재생합니다"
    )
    async def resume(self, interaction: discord.Interaction) -> None:
        if not await self._require_same_voice_channel(interaction):
            return
        if await self.service.resume(interaction.guild.id):
            message = "▶️ 음악을 다시 재생합니다."
        else:
            message = "일시정지된 음악이 없습니다."
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(name="music_skip", description="현재 음악을 건너뜁니다")
    async def skip(self, interaction: discord.Interaction) -> None:
        if not await self._require_same_voice_channel(interaction):
            return
        skipped = await self.service.skip(interaction.guild.id)
        if skipped is None:
            message = "건너뛸 음악이 없습니다."
        else:
            message = f"⏭️ 건너뛰었습니다: {self._format_track(skipped)}"
        await interaction.response.send_message(message)

    @app_commands.command(
        name="music_queue", description="현재 음악 대기열을 표시합니다"
    )
    async def show_queue(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "서버 안에서만 사용할 수 있는 명령어입니다.", ephemeral=True
            )
            return

        snapshot = await self.service.queue_snapshot(interaction.guild.id)
        if snapshot.current is None and not snapshot.queued:
            await interaction.response.send_message("음악 대기열이 비어 있습니다.")
            return

        lines = ["**음악 대기열**"]
        if snapshot.current is not None:
            lines.append(f"지금 재생: {self._format_track(snapshot.current)}")
        else:
            lines.append("지금 재생: 없음")

        if snapshot.queued:
            lines.append("")
            lines.extend(
                f"{index}. {self._format_track(track)}"
                for index, track in enumerate(
                    snapshot.queued[:QUEUE_PREVIEW_LIMIT], start=1
                )
            )
            remaining = len(snapshot.queued) - QUEUE_PREVIEW_LIMIT
            if remaining > 0:
                lines.append(f"…외 {remaining}곡")
        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(
        name="music_stop", description="재생을 중단하고 대기열을 비웁니다"
    )
    async def stop(self, interaction: discord.Interaction) -> None:
        if not await self._require_same_voice_channel(interaction):
            return
        if await self.service.stop(interaction.guild.id):
            message = "⏹️ 재생을 중단하고 대기열을 비웠습니다."
        else:
            message = "중단할 음악이 없습니다."
        await interaction.response.send_message(message)

    @app_commands.command(
        name="music_leave", description="재생을 중단하고 음성 채널에서 나갑니다"
    )
    async def leave(self, interaction: discord.Interaction) -> None:
        if not await self._require_same_voice_channel(interaction):
            return
        await self.service.leave(interaction.guild.id)
        await interaction.response.send_message(
            "👋 재생을 중단하고 음성 채널에서 나갔습니다."
        )
