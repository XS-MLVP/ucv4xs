"""Cold disable is distinct from disabling an already initialized source."""
import pytest

from suites.frontend.bpu.bpu.case.cold_source_isolation import check_cold_source_isolation
from suites.frontend.bpu.bpu.coverage.cold_source_isolation import ColdSourceCoverage
from suites.frontend.bpu.bpu.model.cold_source_isolation import SOURCES, MODES, ColdSourceProgram


@pytest.mark.feature('BPU-INT-101')
@pytest.mark.parametrize('source',SOURCES)
@pytest.mark.parametrize('mode',MODES)
async def test_disabled_cold_source_cannot_override_active_main(bpu_agent,bpu_sc_output,request,source,mode):
    program = ColdSourceProgram(source,mode)
    coverage = ColdSourceCoverage(program)
    try:await check_cold_source_isolation(bpu_agent,program,coverage)
    finally:
        coverage.write(bpu_sc_output)
        coverage.attach_evidence(request.node.user_properties)
