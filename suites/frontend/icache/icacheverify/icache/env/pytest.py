import pytest

from icacheverify.common.env.artifacts import output_directory
from icacheverify.common.env.fixtures import agent_fixture
from icacheverify.icache.agent.main import ICacheAgent

icache_agent = agent_fixture("icache", ICacheAgent, max_batch_ticks=64)


@pytest.fixture
def icache_output(request):
    output = output_directory(request.config.rootpath, "icache")
    output.mkdir(parents=True, exist_ok=True)
    return output
