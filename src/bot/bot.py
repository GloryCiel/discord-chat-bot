"""Discord application bootstrap and command synchronization."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from src.cloud.gcp_instance import GcpInstanceController
from src.cogs.ai_chat import AiChatCog
from src.cogs.general import GeneralCog
from src.cogs.music import MusicCog
from src.cogs.palworld import GameServerCog
from src.config.settings import Settings
from src.integrations.media_extractor import YtDlpMediaExtractor
from src.security.access_policy import ServerControlPolicy
from src.services.chat_sessions import ChatSessionManager
from src.services.music import MusicService
from src.services.palworld import GameServerService


class DiscordBot(commands.Bot):
    def __init__(self, settings: Settings, intents: Optional[discord.Intents] = None):
        if intents is None:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.members = True

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
        )
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self._synced_guild_ids: set[int] = set()

        self.chat_sessions = ChatSessionManager(settings.ai)
        self.music_service = MusicService(YtDlpMediaExtractor())
        self.game_server_service: GameServerService | None = None
        if settings.gcp.enabled:
            try:
                controller = GcpInstanceController(settings.gcp)
                self.game_server_service = GameServerService(controller)
            except Exception:
                self.logger.exception("GCP server control initialization failed")

    async def setup_hook(self) -> None:
        await self.add_cog(AiChatCog(self, self.settings.ai, self.chat_sessions))
        await self.add_cog(GeneralCog(self))
        await self.add_cog(MusicCog(self.music_service))
        await self.add_cog(
            GameServerCog(
                self.game_server_service,
                ServerControlPolicy(self.settings.discord),
                palworld_port=self.settings.gcp.palworld_port,
                rust_port=self.settings.gcp.rust_port,
            )
        )

        synced = await self.tree.sync()
        self.logger.info("Synced %s global Discord commands", len(synced))

    async def on_ready(self) -> None:
        if self.user is None:
            return
        self.logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        if self.game_server_service:
            self.logger.info(
                "GCP server control enabled: %s/%s/%s",
                self.settings.gcp.project_id,
                self.settings.gcp.zone,
                self.settings.gcp.instance_name,
            )
        else:
            self.logger.info("GCP server control disabled")

        for guild in self.guilds:
            await self._sync_guild_commands(guild)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self._sync_guild_commands(guild)

    async def _sync_guild_commands(self, guild: discord.Guild) -> None:
        if guild.id in self._synced_guild_ids:
            return
        try:
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            self._synced_guild_ids.add(guild.id)
            self.logger.info(
                "Synced %s commands to %s (ID: %s)",
                len(synced),
                guild.name,
                guild.id,
            )
        except Exception:
            self.logger.exception("Discord command sync failed for guild %s", guild.id)

    async def close(self) -> None:
        await self.music_service.shutdown()
        await super().close()
