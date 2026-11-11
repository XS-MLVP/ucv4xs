"""SplitCtrl-owned pytest fixtures."""
import pytest

from suites.vector.vagq.testbenches.split.env import session as split_session


@pytest.fixture
async def split_env(native_registration, tmp_path):
    async with split_session(tmp_path, register=native_registration) as env:
        yield env
