import pytest

from icacheverify.common.env.artifacts import output_directory
from icacheverify.common.env.fixtures import agent_fixture
from icacheverify.databank.agent.main import DataBankAgent

databank_agent = agent_fixture("databank", DataBankAgent, max_batch_ticks=64)


@pytest.fixture
def databank_output(request):
    output = output_directory(request.config.rootpath, "databank")
    output.mkdir(parents=True, exist_ok=True)
    return output
