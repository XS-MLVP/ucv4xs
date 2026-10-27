import pytest

from icacheverify.common.env.artifacts import output_directory
from icacheverify.common.env.fixtures import agent_fixture
from icacheverify.prefetchpipe.agent.main import PrefetchPipeAgent

prefetchpipe_agent = agent_fixture("prefetchpipe", PrefetchPipeAgent,
                                   max_batch_ticks=64)


@pytest.fixture
def prefetchpipe_output(request):
    output = output_directory(request.config.rootpath, "prefetchpipe")
    output.mkdir(parents=True, exist_ok=True)
    return output
