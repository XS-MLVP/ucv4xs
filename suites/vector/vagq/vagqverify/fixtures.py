"""Pytest entry points only; the environments own functional components."""
import pytest

from .env import manager_session
from .native import open_dut
from .ordered.env import session as ordered_session
from .pipeline.env import session as pipeline_session
from .pipeline.specs import PIPE1, PIPE3
from .entrytable.env import session as entrytable_session
from .split.env import session as split_session
from .storedata.env import session as storedata_session
from .merge.env import session as merge_session
from .vagq.env import Env as VAGQEnv


@pytest.fixture
def native_registration(request):
    if request.config.getoption('toffee_output', default=None):
        return request.getfixturevalue('toffee_register_dut')
    return None


@pytest.fixture
async def manager_env(native_registration, tmp_path):
    async with manager_session(tmp_path, register=native_registration) as env:
        yield env


@pytest.fixture
def maskgen_dut(native_registration, tmp_path):
    with open_dut('MaskGen', tmp_path, register=native_registration) as dut:
        yield dut


@pytest.fixture
async def ordered_env(native_registration, tmp_path):
    async with ordered_session(tmp_path, register=native_registration) as env:
        yield env


@pytest.fixture
async def pipeline_env(native_registration, tmp_path):
    async with pipeline_session(tmp_path, PIPE1, register=native_registration) as env:
        yield env


@pytest.fixture
async def pipeline3_env(native_registration, tmp_path):
    async with pipeline_session(tmp_path, PIPE3, register=native_registration) as env:
        yield env


@pytest.fixture
async def entrytable_env(native_registration, tmp_path):
    async with entrytable_session(tmp_path, register=native_registration) as env:
        yield env


@pytest.fixture
async def split_env(native_registration, tmp_path):
    async with split_session(tmp_path, register=native_registration) as env:
        yield env


@pytest.fixture
async def storedata_env(native_registration, tmp_path):
    async with storedata_session(tmp_path, register=native_registration) as env:
        yield env


@pytest.fixture
async def merge_env(native_registration, tmp_path):
    async with merge_session(tmp_path, register=native_registration) as env:
        yield env


@pytest.fixture
def arbiter_dut(native_registration, tmp_path):
    with open_dut('VAGQArbiter', tmp_path, register=native_registration) as dut:
        yield dut


@pytest.fixture
def vagq_env(native_registration, tmp_path):
    with open_dut('VAGQ', tmp_path, clocked=True, register=native_registration) as dut:
        yield VAGQEnv.create(dut)


@pytest.fixture
def manager_dut(native_registration, tmp_path):
    with open_dut('VAGQManager', tmp_path, clocked=True,
                  register=native_registration) as dut:
        yield dut


@pytest.fixture
def addrgen_dut(native_registration, tmp_path):
    with open_dut('AddrGen', tmp_path, register=native_registration) as dut:
        yield dut
