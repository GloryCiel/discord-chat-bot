"""Selectable game-server slash commands."""

import logging
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from src.domain.palworld import GameKind, InstanceState
from src.security.access_policy import ServerControlPolicy
from src.services.palworld import GameServerService, GameSwitchRequired


class GameServerCog(commands.Cog):
    def __init__(
        self,
        service: GameServerService | None,
        policy: ServerControlPolicy,
        palworld_port: int = 8211,
        rust_port: int = 28015,
    ):
        self.service = service
        self.policy = policy
        self.ports = {
            GameKind.PALWORLD: palworld_port,
            GameKind.RUST: rust_port,
        }
        self.logger = logging.getLogger(__name__)

    async def _authorized_service(
        self, interaction: discord.Interaction
    ) -> GameServerService | None:
        if not self.service:
            await interaction.response.send_message(
                "게임 서버 제어가 아직 구성되지 않았습니다.", ephemeral=True
            )
            return None
        if not self.policy.allows(interaction):
            await interaction.response.send_message(
                "이 서버를 제어할 권한이 없습니다.", ephemeral=True
            )
            return None
        return self.service

    def _format_state(self, state: InstanceState) -> str:
        labels = {
            "RUNNING": "실행 중",
            "TERMINATED": "꺼짐",
            "STOPPING": "종료 중",
            "STAGING": "시작 준비 중",
            "PROVISIONING": "프로비저닝 중",
        }
        status = labels.get(state.status, state.status)
        game = state.selected_game
        game_text = game.label if game else "선택되지 않음"
        address = ""
        if state.external_ip and game:
            address = f"\n접속 주소: `{state.external_ip}:{self.ports[game]}`"
        return f"VM 상태: **{status}**\n선택 게임: **{game_text}**{address}"

    @app_commands.command(
        name="game_server_status", description="GCP 게임 서버 상태를 확인합니다"
    )
    async def status(self, interaction: discord.Interaction) -> None:
        service = await self._authorized_service(interaction)
        if not service:
            return
        await interaction.response.defer(thinking=True)
        try:
            state = await service.status()
            await interaction.followup.send(self._format_state(state))
        except Exception:
            self.logger.exception("GCP status failed")
            await interaction.followup.send("GCP 서버 상태 확인에 실패했습니다.")

    @app_commands.command(
        name="game_server_start", description="팰월드 또는 러스트 서버를 시작합니다"
    )
    @app_commands.describe(game="시작할 게임")
    async def start(
        self,
        interaction: discord.Interaction,
        game: Literal["palworld", "rust"],
    ) -> None:
        service = await self._authorized_service(interaction)
        if not service:
            return
        await interaction.response.defer(thinking=True)
        try:
            selected = GameKind(game)
            result = await service.start(selected)
            prefix = (
                "이미 실행 중입니다.\n"
                if result.already_running
                else f"VM을 시작했습니다. {selected.label} 서버가 준비될 때까지 잠시 기다려 주세요.\n"
            )
            await interaction.followup.send(prefix + self._format_state(result.state))
        except GameSwitchRequired as exc:
            current = exc.current.label if exc.current else "알 수 없는 게임"
            await interaction.followup.send(
                f"현재 **{current}** 서버가 실행 중입니다. 먼저 "
                "`/game_server_stop confirm:True`로 종료한 뒤 다시 시도하세요."
            )
        except Exception:
            self.logger.exception("GCP start failed")
            await interaction.followup.send("GCP 서버 시작에 실패했습니다.")

    @app_commands.command(
        name="game_server_stop", description="게임 서버와 GCP VM을 정상 종료합니다"
    )
    @app_commands.describe(confirm="접속자가 모두 나갔고 종료해도 되면 체크")
    async def stop(
        self, interaction: discord.Interaction, confirm: bool = False
    ) -> None:
        service = await self._authorized_service(interaction)
        if not service:
            return
        if not confirm:
            await interaction.response.send_message(
                "종료하지 않았습니다. 접속자가 모두 나갔는지 확인한 뒤 "
                "`confirm`을 `True`로 선택해 다시 실행하세요.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True)
        try:
            result = await service.stop()
            prefix = (
                "이미 꺼져 있습니다.\n"
                if result.already_stopped
                else "게임 서버의 정상 종료 절차를 거쳐 VM이 꺼졌습니다.\n"
            )
            await interaction.followup.send(prefix + self._format_state(result.state))
        except Exception:
            self.logger.exception("GCP stop failed")
            await interaction.followup.send("GCP 서버 종료에 실패했습니다.")


# Backward-compatible import path while the module is renamed later.
PalworldCog = GameServerCog
