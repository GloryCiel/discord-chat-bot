import unittest

from src.domain.palworld import GameKind, InstanceState
from src.services.palworld import GameServerService, GameSwitchRequired


class FakeController:
    def __init__(self, status: str, game: GameKind | None = None):
        self.state = InstanceState(
            status=status, external_ip=None, selected_game=game
        )
        self.start_calls = 0
        self.stop_calls = 0

    async def get(self) -> InstanceState:
        return self.state

    async def start(self, game: GameKind) -> InstanceState:
        self.start_calls += 1
        self.state = InstanceState(
            status="RUNNING",
            external_ip="127.0.0.1",
            selected_game=game,
        )
        return self.state

    async def stop(self) -> InstanceState:
        self.stop_calls += 1
        self.state = InstanceState(status="TERMINATED", external_ip=None)
        return self.state


class GameServerServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_is_idempotent_when_vm_is_running(self) -> None:
        controller = FakeController("RUNNING", GameKind.PALWORLD)
        service = GameServerService(controller)

        result = await service.start(GameKind.PALWORLD)

        self.assertTrue(result.already_running)
        self.assertEqual(controller.start_calls, 0)

    async def test_start_and_stop_delegate_to_controller(self) -> None:
        controller = FakeController("TERMINATED")
        service = GameServerService(controller)

        started = await service.start(GameKind.RUST)
        stopped = await service.stop()

        self.assertFalse(started.already_running)
        self.assertEqual(started.state.status, "RUNNING")
        self.assertEqual(started.state.selected_game, GameKind.RUST)
        self.assertFalse(stopped.already_stopped)
        self.assertEqual(stopped.state.status, "TERMINATED")
        self.assertEqual(controller.start_calls, 1)
        self.assertEqual(controller.stop_calls, 1)

    async def test_stop_is_idempotent_when_vm_is_stopped(self) -> None:
        controller = FakeController("TERMINATED")
        service = GameServerService(controller)

        result = await service.stop()

        self.assertTrue(result.already_stopped)
        self.assertEqual(controller.stop_calls, 0)

    async def test_running_vm_requires_stop_before_switching_games(self) -> None:
        controller = FakeController("RUNNING", GameKind.PALWORLD)
        service = GameServerService(controller)

        with self.assertRaises(GameSwitchRequired):
            await service.start(GameKind.RUST)

        self.assertEqual(controller.start_calls, 0)
