"""OrderedPermitCtrl-owned pytest fixtures."""
import pytest

from suites.vector.vagq.testbenches.ordered.env import session as ordered_session


@pytest.fixture
async def ordered_env(native_registration, tmp_path):
    async with ordered_session(tmp_path, register=native_registration) as env:
        yield env
