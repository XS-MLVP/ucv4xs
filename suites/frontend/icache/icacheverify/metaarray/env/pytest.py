import pytest

from icacheverify.common.env.artifacts import output_directory
from icacheverify.common.env.fixtures import agent_fixture
from icacheverify.metaarray.agent.main import MetaArrayAgent

metaarray_agent = agent_fixture("metaarray", MetaArrayAgent, max_batch_ticks=64)


@pytest.fixture
def metaarray_output(request):
    output = output_directory(request.config.rootpath, "metaarray")
    output.mkdir(parents=True, exist_ok=True)
    return output
