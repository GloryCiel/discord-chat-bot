"""Discord authorization policy for infrastructure control commands."""

import discord

from src.config.settings import DiscordSettings


class ServerControlPolicy:
    def __init__(self, settings: DiscordSettings):
        self.settings = settings

    def allows(self, interaction: discord.Interaction) -> bool:
        guild_id = self.settings.control_guild_id
        if guild_id and interaction.guild_id != guild_id:
            return False

        users = self.settings.control_user_ids
        roles = self.settings.control_role_ids
        if not users and not roles:
            return True
        if interaction.user.id in users:
            return True
        if isinstance(interaction.user, discord.Member):
            if interaction.user.guild_permissions.administrator:
                return True
            user_roles = {role.id for role in interaction.user.roles}
            return bool(user_roles & roles)
        return False
