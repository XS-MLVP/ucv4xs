"""AheadBTB state witness output registered by the suite root."""
import pytest

from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT


@pytest.fixture
def abtb_state_output():
    output = output_directory(REPO_ROOT, 'abtb')
    output.mkdir(parents=True, exist_ok=True)
    return output
