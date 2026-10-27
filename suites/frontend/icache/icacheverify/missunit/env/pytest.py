import pytest

from icacheverify.common.env.artifacts import output_directory
from icacheverify.common.env.fixtures import agent_fixture
from icacheverify.missunit.agent.main import MissUnitAgent

missunit_agent = agent_fixture("missunit", MissUnitAgent, max_batch_ticks=64)


@pytest.fixture
def missunit_output(request):
    output = output_directory(request.config.rootpath, "missunit")
    output.mkdir(parents=True, exist_ok=True)
    return output
