"""NewPipelineConnectPipe_3-owned pytest fixtures."""
import pytest

from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.env import session as pipeline_session
from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.env.specs import PIPE3


@pytest.fixture
async def pipeline3_env(native_registration, tmp_path):
    async with pipeline_session(tmp_path, PIPE3, register=native_registration) as env:
        yield env
