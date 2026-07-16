"""Palworld VM orchestration independent from Discord interactions."""

import asyncio
from dataclasses import dataclass
from typing import Protocol

from src.domain.palworld import InstanceState


class InstanceController(Protocol):
    async def get(self) -> InstanceState: ...

    async def start(self) -> InstanceState: ...

    async def stop(self) -> InstanceState: ...


@dataclass(frozen=True)
class StartResult:
    state: InstanceState
    already_running: bool


@dataclass(frozen=True)
class StopResult:
    state: InstanceState
    already_stopped: bool


class PalworldService:
    def __init__(self, controller: InstanceController):
        self.controller = controller
        self._operation_lock = asyncio.Lock()

    async def status(self) -> InstanceState:
        return await self.controller.get()

    async def start(self) -> StartResult:
        async with self._operation_lock:
            before = await self.controller.get()
            if before.status == "RUNNING":
                return StartResult(state=before, already_running=True)
            state = await self.controller.start()
            return StartResult(state=state, already_running=False)

    async def stop(self) -> StopResult:
        async with self._operation_lock:
            before = await self.controller.get()
            if before.status == "TERMINATED":
                return StopResult(state=before, already_stopped=True)
            state = await self.controller.stop()
            return StopResult(state=state, already_stopped=False)
