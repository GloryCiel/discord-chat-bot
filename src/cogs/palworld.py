"""Palworld server slash commands."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from src.domain.palworld import InstanceState
from src.security.access_policy import ServerControlPolicy
from src.services.palworld import PalworldService


class PalworldCog(commands.Cog):
    def __init__(
        self,
        service: PalworldService | None,
        policy: ServerControlPolicy,
    ):
        self.service = service
        self.policy = policy
        self.logger = logging.getLogger(__name__)

    async def _authorized_service(
        self, interaction: discord.Interaction
    ) -> PalworldService | None:
        if not self.service:
            await interaction.response.send_message(
                "팰월드 서버 제어가 아직 구성되지 않았습니다.", ephemeral=True
            )
            return None
        if not self.policy.allows(interaction):
            await interaction.response.send_message(
                "이 서버를 제어할 권한이 없습니다.", ephemeral=True
            )
            return None
        return self.service

    @staticmethod
    def _format_state(state: InstanceState) -> str:
        labels = {
            "RUNNING": "실행 중",
            "TERMINATED": "꺼짐",
            "STOPPING": "종료 중",
            "STAGING": "시작 준비 중",
            "PROVISIONING": "프로비저닝 중",
        }
        status = labels.get(state.status, state.status)
        address = (
            f"\n접속 주소: `{state.external_ip}:8211`" if state.external_ip else ""
        )
        return f"VM 상태: **{status}**{address}"

    @app_commands.command(
        name="pal_server_status", description="팰월드 GCP 서버 상태를 확인합니다"
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
        name="pal_server_start", description="팰월드 GCP 서버를 시작합니다"
    )
    async def start(self, interaction: discord.Interaction) -> None:
        service = await self._authorized_service(interaction)
        if not service:
            return
        await interaction.response.defer(thinking=True)
        try:
            result = await service.start()
            prefix = (
                "이미 실행 중입니다.\n"
                if result.already_running
                else "VM을 시작했습니다. 팰월드 업데이트와 서버 시작에 1~3분 정도 걸릴 수 있습니다.\n"
            )
            await interaction.followup.send(prefix + self._format_state(result.state))
        except Exception:
            self.logger.exception("GCP start failed")
            await interaction.followup.send("GCP 서버 시작에 실패했습니다.")

    @app_commands.command(
        name="pal_server_stop", description="팰월드를 저장하고 GCP 서버를 종료합니다"
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
                else "팰월드 저장 종료를 요청했고 VM이 꺼졌습니다.\n"
            )
            await interaction.followup.send(prefix + self._format_state(result.state))
        except Exception:
            self.logger.exception("GCP stop failed")
            await interaction.followup.send("GCP 서버 종료에 실패했습니다.")
