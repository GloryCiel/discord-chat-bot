"""Minimal GCP Compute Engine controller for the Palworld VM."""

import asyncio
import base64
import json
import google.auth
from google.cloud import compute_v1
from google.oauth2 import service_account

from src.config.settings import GcpSettings
from src.domain.palworld import InstanceState


class GcpInstanceController:
    def __init__(self, settings: GcpSettings):
        self.project = settings.project_id
        self.zone = settings.zone
        self.instance_name = settings.instance_name
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
        for interface in instance.network_interfaces:
            for access_config in interface.access_configs:
                if access_config.nat_i_p:
                    external_ip = access_config.nat_i_p
                    break
            if external_ip:
                break
        return InstanceState(status=instance.status, external_ip=external_ip)

    async def get(self) -> InstanceState:
        return await asyncio.to_thread(self._get_sync)

    async def start(self) -> InstanceState:
        def start_sync() -> None:
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
