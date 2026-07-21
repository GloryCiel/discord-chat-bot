"""GCP Compute Engine controller for a selectable game-server VM."""

import asyncio
import base64
import json
import google.auth
from google.cloud import compute_v1
from google.oauth2 import service_account

from src.config.settings import GcpSettings
from src.domain.palworld import GameKind, InstanceState


class GcpInstanceController:
    def __init__(self, settings: GcpSettings):
        self.project = settings.project_id
        self.zone = settings.zone
        self.instance_name = settings.instance_name
        self.game_metadata_key = settings.game_metadata_key
        credentials = self._load_credentials(settings)
        self.client = compute_v1.InstancesClient(credentials=credentials)

    @staticmethod
    def _load_credentials(settings: GcpSettings):
        scopes = ["https://www.googleapis.com/auth/compute"]
        encoded = settings.service_account_json_base64
        if encoded:
            try:
                info = json.loads(base64.b64decode(encoded).decode("utf-8"))
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Invalid GCP_SERVICE_ACCOUNT_JSON_BASE64") from exc
            return service_account.Credentials.from_service_account_info(
                info, scopes=scopes
            )

        if settings.application_credentials:
            return service_account.Credentials.from_service_account_file(
                settings.application_credentials, scopes=scopes
            )

        credentials, _ = google.auth.default(scopes=scopes)
        return credentials

    def _get_sync(self) -> InstanceState:
        instance = self.client.get(
            project=self.project,
            zone=self.zone,
            instance=self.instance_name,
        )
        external_ip = None
        selected_game = None
        if instance.metadata:
            for item in instance.metadata.items or []:
                if item.key == self.game_metadata_key:
                    selected_game = GameKind.parse(item.value)
                    break
        for interface in instance.network_interfaces:
            for access_config in interface.access_configs:
                if access_config.nat_i_p:
                    external_ip = access_config.nat_i_p
                    break
            if external_ip:
                break
        return InstanceState(
            status=instance.status,
            external_ip=external_ip,
            selected_game=selected_game,
        )

    async def get(self) -> InstanceState:
        return await asyncio.to_thread(self._get_sync)

    def _select_game_sync(self, game: GameKind) -> None:
        instance = self.client.get(
            project=self.project,
            zone=self.zone,
            instance=self.instance_name,
        )
        current_metadata = instance.metadata or compute_v1.Metadata()
        metadata = compute_v1.Metadata()
        metadata.fingerprint = current_metadata.fingerprint
        metadata.items = [
            item
            for item in (current_metadata.items or [])
            if item.key != self.game_metadata_key
        ]
        selected = compute_v1.Items()
        selected.key = self.game_metadata_key
        selected.value = game.value
        metadata.items.append(selected)
        operation = self.client.set_metadata(
            project=self.project,
            zone=self.zone,
            instance=self.instance_name,
            metadata_resource=metadata,
        )
        operation.result(timeout=180)

    async def start(self, game: GameKind) -> InstanceState:
        def start_sync() -> None:
            self._select_game_sync(game)
            operation = self.client.start(
                project=self.project,
                zone=self.zone,
                instance=self.instance_name,
            )
            operation.result(timeout=180)

        await asyncio.to_thread(start_sync)
        return await self.get()

    async def stop(self) -> InstanceState:
        def stop_sync() -> None:
            operation = self.client.stop(
                project=self.project,
                zone=self.zone,
                instance=self.instance_name,
            )
            operation.result(timeout=240)

        await asyncio.to_thread(stop_sync)
        return await self.get()
