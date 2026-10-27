from bpuverify.abtb.agent.main import AbtbAgent
import pytest
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.common.env.fixtures import agent_fixture
from bpuverify.common.env.artifacts import output_directory

abtb_agent = agent_fixture("abtb", AbtbAgent, max_batch_ticks=128)


@pytest.fixture
def abtb_state_output():
    output = output_directory(REPO_ROOT, 'abtb')
    output.mkdir(parents=True, exist_ok=True)
    return output
