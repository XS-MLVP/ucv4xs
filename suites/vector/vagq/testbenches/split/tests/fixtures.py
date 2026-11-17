"""SplitCtrl-owned pytest fixtures."""
import pytest


@pytest.fixture
async def split_env(native_registration, tmp_path):
    from suites.vector.vagq.testbenches.split.env import session as split_session

    async with split_session(tmp_path, register=native_registration) as env:
        yield env
