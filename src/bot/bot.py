"""
Main Discord bot class implementation
"""
import discord
from discord import app_commands
from typing import Optional, Dict
from src.ai.chat_handler import ChatHandler
from src.cloud.gcp_instance import GcpInstanceController, InstanceState
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
        self.active_users = set()  # 활성화된 사용자 ID 저장
        self.server_controller: Optional[GcpInstanceController] = None
        if self.settings.server_control_enabled:
            try:
                self.server_controller = GcpInstanceController(self.settings)
            except Exception as exc:
                print(f"GCP server control disabled: {exc}")

    def can_control_server(self, interaction: discord.Interaction) -> bool:
        allowed_guild_id = self.settings.discord_control_guild_id
        if allowed_guild_id and interaction.guild_id != allowed_guild_id:
            return False

        user_id = interaction.user.id
        restricted_users = self.settings.discord_control_user_ids
        restricted_roles = self.settings.discord_control_role_ids
        if not restricted_users and not restricted_roles:
            return True
        if user_id in restricted_users:
            return True
        if isinstance(interaction.user, discord.Member):
            if interaction.user.guild_permissions.administrator:
                return True
            return bool(
                {role.id for role in interaction.user.roles} & restricted_roles
            )
        return False

    async def require_server_control(
        self, interaction: discord.Interaction
    ) -> bool:
        if not self.server_controller:
            await interaction.response.send_message(
                "팰월드 서버 제어가 아직 구성되지 않았습니다.", ephemeral=True
            )
            return False
        if not self.can_control_server(interaction):
            await interaction.response.send_message(
                "이 서버를 제어할 권한이 없습니다.", ephemeral=True
            )
            return False
        return True

    @staticmethod
    def format_instance_state(state: InstanceState) -> str:
        labels = {
            "RUNNING": "실행 중",
            "TERMINATED": "꺼짐",
            "STOPPING": "종료 중",
            "STAGING": "시작 준비 중",
            "PROVISIONING": "프로비저닝 중",
        }
        status = labels.get(state.status, state.status)
        address = f"\n접속 주소: `{state.external_ip}:8211`" if state.external_ip else ""
        return f"VM 상태: **{status}**{address}"
        
    async def setup_hook(self) -> None:
        """Initialize bot commands and other setup tasks"""
        # Add commands here
        @self.tree.command(name="chat", description="Start a new chat session")
        async def chat(interaction: discord.Interaction):
            if not self.settings.ai_enabled:
                await interaction.response.send_message(
                    "AI 채팅이 비활성화되어 있습니다. 관리자에게 GROQ_API_KEY 설정을 요청하세요.",
                    ephemeral=True,
                )
                return
            user_id = interaction.user.id
            self.active_users.add(user_id)  # 사용자 활성화
            await interaction.response.send_message("이제 AI와 대화할 수 있습니다! (/end로 종료)")
        
        @self.tree.command(name="end", description="End the chat session for you")
        async def end(interaction: discord.Interaction):
            user_id = interaction.user.id
            if user_id in self.active_users:
                self.active_users.remove(user_id)
                handler = self.chat_handlers.get(interaction.channel_id)
                if handler:
                    await handler.reset_chat()
                await interaction.response.send_message("AI와의 대화가 종료되었습니다. 다시 시작하려면 /chat을 입력하세요.")
            else:
                await interaction.response.send_message("이미 비활성화되어 있습니다. /chat으로 다시 시작할 수 있습니다.")
        
        @self.tree.command(name="help", description="Show available commands")
        async def help(interaction: discord.Interaction):
            help_text = """
            **사용 가능한 명령어:**
            `/chat` - AI와의 대화 시작
            `/end` - AI와의 대화 종료
            `/help` - 도움말 표시
            `/pal_server_status` - 팰월드 서버 상태 확인
            `/pal_server_start` - 팰월드 서버 시작
            `/pal_server_stop` - 팰월드 저장 후 서버 종료
            
            **일반 채팅:**
            `/chat` 명령어를 사용한 사용자만 AI와 대화할 수 있습니다.
            """
            await interaction.response.send_message(help_text)

        @self.tree.command(name="pal_server_status", description="팰월드 GCP 서버 상태를 확인합니다")
        async def pal_server_status(interaction: discord.Interaction):
            if not await self.require_server_control(interaction):
                return
            await interaction.response.defer(thinking=True)
            try:
                state = await self.server_controller.get()
                await interaction.followup.send(self.format_instance_state(state))
            except Exception as exc:
                print(f"GCP status error: {exc}")
                await interaction.followup.send("GCP 서버 상태 확인에 실패했습니다.")

        @self.tree.command(name="pal_server_start", description="팰월드 GCP 서버를 시작합니다")
        async def pal_server_start(interaction: discord.Interaction):
            if not await self.require_server_control(interaction):
                return
            await interaction.response.defer(thinking=True)
            try:
                before = await self.server_controller.get()
                state = await self.server_controller.start()
                prefix = "이미 실행 중입니다.\n" if before.status == "RUNNING" else (
                    "VM을 시작했습니다. 팰월드 업데이트와 서버 시작에 1~3분 정도 걸릴 수 있습니다.\n"
                )
                await interaction.followup.send(
                    prefix + self.format_instance_state(state)
                )
            except Exception as exc:
                print(f"GCP start error: {exc}")
                await interaction.followup.send("GCP 서버 시작에 실패했습니다.")

        @self.tree.command(name="pal_server_stop", description="팰월드를 저장하고 GCP 서버를 종료합니다")
        @app_commands.describe(confirm="접속자가 모두 나갔고 종료해도 되면 체크")
        async def pal_server_stop(
            interaction: discord.Interaction, confirm: bool = False
        ):
            if not await self.require_server_control(interaction):
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
                state = await self.server_controller.stop()
                await interaction.followup.send(
                    "팰월드 저장 종료를 요청했고 VM이 꺼졌습니다.\n"
                    + self.format_instance_state(state)
                )
            except Exception as exc:
                print(f"GCP stop error: {exc}")
                await interaction.followup.send("GCP 서버 종료에 실패했습니다.")
        
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
        
        # 활성화된 사용자가 아니면 무시
        if message.author.id not in self.active_users:
            return
        
        # Get chat handler for this channel
        chat_handler = await self.get_chat_handler(message.channel.id)
        
        # Generate and send response
        async with message.channel.typing():
            response = await chat_handler.process_message(message.content)
            chunks = [response[i:i + 1900] for i in range(0, len(response), 1900)] or [response]
            for index, chunk in enumerate(chunks):
                if index == 0:
                    await message.reply(chunk)
                else:
                    await message.channel.send(chunk)
