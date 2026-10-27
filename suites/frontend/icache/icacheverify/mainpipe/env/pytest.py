import pytest

from icacheverify.common.env.artifacts import output_directory
from icacheverify.common.env.fixtures import agent_fixture
from icacheverify.mainpipe.agent.main import MainPipeAgent

mainpipe_agent = agent_fixture("mainpipe", MainPipeAgent, max_batch_ticks=64)


@pytest.fixture
def mainpipe_output(request):
    output = output_directory(request.config.rootpath, "mainpipe")
    output.mkdir(parents=True, exist_ok=True)
    return output
