"""NewPipelineConnectPipe-owned pytest fixtures for both specializations."""
import pytest

from suites.vector.vagq.testbenches.pipeline.env import session as pipeline_session
from suites.vector.vagq.testbenches.pipeline.env.specs import PIPE1
from suites.vector.vagq.testbenches.pipeline.env.specs import PIPE3


@pytest.fixture
async def pipeline_env(native_registration, tmp_path):
    async with pipeline_session(tmp_path, PIPE1, register=native_registration) as env:
        yield env


@pytest.fixture
async def pipeline3_env(native_registration, tmp_path):
    async with pipeline_session(tmp_path, PIPE3, register=native_registration) as env:
        yield env
