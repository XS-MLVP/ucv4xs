"""Register testbench-owned fixtures here; keep one suite pytest root."""
import pytest

pytest_plugins = ("ucv.pytest_selftest",)


@pytest.fixture
def dut_fixture():
    """Replace with the real owner fixture bound to the generated DUT."""
    pytest.fail("TODO: bind the generated DUT and register its owner fixture")
