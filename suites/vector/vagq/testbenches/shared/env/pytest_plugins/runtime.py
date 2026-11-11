"""Cross-testbench pytest fixtures from the shared environment."""
import pytest


@pytest.fixture
def native_registration(request):
    if request.config.getoption('toffee_output', default=None):
        return request.getfixturevalue('toffee_register_dut')
    return None
