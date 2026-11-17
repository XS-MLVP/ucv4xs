"""NewPipelineConnectPipe-owned pytest fixtures."""
import pytest

from suites.vector.vagq.testbenches.NewPipelineConnectPipe.env import session as pipeline_session
from suites.vector.vagq.testbenches.NewPipelineConnectPipe.env.specs import PIPE1


@pytest.fixture
async def pipeline_env(native_registration, tmp_path):
    async with pipeline_session(tmp_path, PIPE1, register=native_registration) as env:
        yield env
