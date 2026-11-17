"""Top-level VAGQ-owned pytest fixtures."""
import pytest

from suites.vector.vagq.testbenches.shared.env.native import open_dut


@pytest.fixture
def vagq_env(native_registration, tmp_path):
    with open_dut('VAGQ', tmp_path, clocked=True, register=native_registration) as dut:
        from suites.vector.vagq.testbenches.vagq.env import Env as VAGQEnv

        yield VAGQEnv.create(dut)
