import pytest

from icacheverify.common.env.artifacts import output_directory
from icacheverify.common.env.fixtures import agent_fixture
from icacheverify.dataarray.agent.main import DataArrayAgent

dataarray_agent = agent_fixture("dataarray", DataArrayAgent, max_batch_ticks=64)


@pytest.fixture
def dataarray_output(request):
    output = output_directory(request.config.rootpath, "dataarray")
    output.mkdir(parents=True, exist_ok=True)
    return output
