"""MergeCtrl-owned pytest fixtures."""
import pytest

from suites.vector.vagq.testbenches.merge.env import session as merge_session


@pytest.fixture
async def merge_env(native_registration, tmp_path):
    async with merge_session(tmp_path, register=native_registration) as env:
        yield env
