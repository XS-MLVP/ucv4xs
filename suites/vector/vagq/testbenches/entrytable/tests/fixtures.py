"""VAGQEntryTable-owned pytest fixtures."""
import pytest

from suites.vector.vagq.testbenches.entrytable.env import session as entrytable_session


@pytest.fixture
async def entrytable_env(native_registration, tmp_path):
    async with entrytable_session(tmp_path, register=native_registration) as env:
        yield env
