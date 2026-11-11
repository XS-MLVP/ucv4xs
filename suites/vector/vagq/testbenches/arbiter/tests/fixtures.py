"""VAGQArbiter-owned pytest fixtures."""
import pytest

from suites.vector.vagq.testbenches.arbiter.env import Env
from suites.vector.vagq.testbenches.shared.env.native import open_dut


@pytest.fixture
def arbiter_env(native_registration, tmp_path):
    with open_dut('VAGQArbiter', tmp_path, register=native_registration) as dut:
        yield Env.create(dut)
