"""Integrated BPU state witness output registered by the suite root."""
import pytest

from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory


@pytest.fixture
def bpu_sc_output(request):
    """Keep SC state witnesses beside this run's other BPU artifacts."""
    output = output_directory(request.config.rootpath, 'bpu')
    output.mkdir(parents=True, exist_ok=True)
    return output
