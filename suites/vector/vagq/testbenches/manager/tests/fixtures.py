"""VAGQManager-owned pytest fixtures."""
import pytest

from suites.vector.vagq.testbenches.manager.env.base import manager_session
from suites.vector.vagq.testbenches.shared.env.native import open_dut


@pytest.fixture
async def manager_env(native_registration, tmp_path):
    async with manager_session(tmp_path, register=native_registration) as env:
        yield env


@pytest.fixture
def manager_dut(native_registration, tmp_path):
    with open_dut('VAGQManager', tmp_path, clocked=True,
                  register=native_registration) as dut:
        yield dut
