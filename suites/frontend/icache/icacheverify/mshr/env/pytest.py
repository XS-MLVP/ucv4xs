import pytest

from icacheverify.common.env.artifacts import output_directory
from icacheverify.common.env.fixtures import agent_fixture
from icacheverify.mshr.agent.main import MshrAgent

mshr_agent = agent_fixture("mshr", MshrAgent, max_batch_ticks=64)


@pytest.fixture
def mshr_output(request):
    output = output_directory(request.config.rootpath, "mshr")
    output.mkdir(parents=True, exist_ok=True)
    return output
