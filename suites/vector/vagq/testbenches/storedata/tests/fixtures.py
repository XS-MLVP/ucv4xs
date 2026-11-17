"""StoreDataCtrl-owned pytest fixtures."""
import pytest


@pytest.fixture
async def storedata_env(native_registration, tmp_path):
    from suites.vector.vagq.testbenches.storedata.env import session as storedata_session

    async with storedata_session(tmp_path, register=native_registration) as env:
        yield env
