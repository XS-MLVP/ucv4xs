import pytest

from icacheverify.common.env.artifacts import output_directory
from icacheverify.common.env.fixtures import agent_fixture
from icacheverify.metabank.agent.main import MetaBankAgent

metabank_agent = agent_fixture("metabank", MetaBankAgent, max_batch_ticks=64)


@pytest.fixture
def metabank_output(request):
    output = output_directory(request.config.rootpath, "metabank")
    output.mkdir(parents=True, exist_ok=True)
    return output
