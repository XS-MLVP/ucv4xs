import pytest

from icacheverify.common.env.artifacts import output_directory
from icacheverify.common.env.fixtures import agent_fixture
from icacheverify.replacer.agent.main import ReplacerAgent

replacer_agent = agent_fixture("replacer", ReplacerAgent, max_batch_ticks=64)


@pytest.fixture
def replacer_output(request):
    output = output_directory(request.config.rootpath, "replacer")
    output.mkdir(parents=True, exist_ok=True)
    return output
