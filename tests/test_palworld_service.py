import unittest

from src.domain.palworld import InstanceState
from src.services.palworld import PalworldService


class FakeController:
    def __init__(self, status: str):
        self.state = InstanceState(status=status, external_ip=None)
        self.start_calls = 0
        self.stop_calls = 0

    async def get(self) -> InstanceState:
        return self.state

    async def start(self) -> InstanceState:
        self.start_calls += 1
        self.state = InstanceState(status="RUNNING", external_ip="127.0.0.1")
        return self.state

    async def stop(self) -> InstanceState:
        self.stop_calls += 1
        self.state = InstanceState(status="TERMINATED", external_ip=None)
        return self.state


class PalworldServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_is_idempotent_when_vm_is_running(self) -> None:
        controller = FakeController("RUNNING")
        service = PalworldService(controller)

        result = await service.start()

        self.assertTrue(result.already_running)
        self.assertEqual(controller.start_calls, 0)

    async def test_start_and_stop_delegate_to_controller(self) -> None:
        controller = FakeController("TERMINATED")
        service = PalworldService(controller)

        started = await service.start()
        stopped = await service.stop()

        self.assertFalse(started.already_running)
        self.assertEqual(started.state.status, "RUNNING")
        self.assertFalse(stopped.already_stopped)
        self.assertEqual(stopped.state.status, "TERMINATED")
        self.assertEqual(controller.start_calls, 1)
        self.assertEqual(controller.stop_calls, 1)

    async def test_stop_is_idempotent_when_vm_is_stopped(self) -> None:
        controller = FakeController("TERMINATED")
        service = PalworldService(controller)

        result = await service.stop()

        self.assertTrue(result.already_stopped)
        self.assertEqual(controller.stop_calls, 0)
