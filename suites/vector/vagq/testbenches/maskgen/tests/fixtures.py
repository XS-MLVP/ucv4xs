"""MaskGen-owned pytest fixtures."""
import pytest

from suites.vector.vagq.testbenches.shared.env.native import open_dut


@pytest.fixture
def maskgen_dut(native_registration, tmp_path):
    with open_dut('MaskGen', tmp_path, register=native_registration) as dut:
        yield dut
