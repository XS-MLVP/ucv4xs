import pytest

from icacheverify.common.env.artifacts import output_directory
from icacheverify.common.env.fixtures import agent_fixture
from icacheverify.waylookup.agent.main import WayLookupAgent

waylookup_agent = agent_fixture("waylookup", WayLookupAgent, max_batch_ticks=64)


@pytest.fixture
def waylookup_output(request):
    """Keep per-run artifacts beside the other way-lookup outputs."""
    output = output_directory(request.config.rootpath, "waylookup")
    output.mkdir(parents=True, exist_ok=True)
    return output
