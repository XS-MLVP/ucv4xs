import pytest

from bpuverify.bpu.agent.main import BpuAgent
from bpuverify.common.env.fixtures import agent_fixture
from bpuverify.common.env.artifacts import output_directory

bpu_agent = agent_fixture("bpu", BpuAgent, max_batch_ticks=256)


@pytest.fixture
def bpu_sc_output(request):
    """Keep SC state witnesses beside this run's other BPU artifacts."""
    output = output_directory(request.config.rootpath, 'bpu')
    output.mkdir(parents=True, exist_ok=True)
    return output
