"""Register this verification package's fixtures and reports."""
import pytest

pytest_plugins = (
    "ucv.pytest_selftest",
)


@pytest.fixture
def dut_fixture():
    pytest.fail("TODO: bind the generated DUT and register its owner fixture")
