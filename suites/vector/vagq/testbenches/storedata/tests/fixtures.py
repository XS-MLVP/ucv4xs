"""StoreDataCtrl-owned pytest fixtures."""
import pytest

from suites.vector.vagq.testbenches.storedata.env import session as storedata_session


@pytest.fixture
async def storedata_env(native_registration, tmp_path):
    async with storedata_session(tmp_path, register=native_registration) as env:
        yield env
