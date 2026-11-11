"""Composed BPU: late feedback without an original ITTAGE snapshot must not learn."""
import json

import pytest

from suites.frontend.bpu.testbenches.bpu.coverage.late_source import LateSourceCoverage

LATE_PC = 0x4000_1800
POSITION = 4
TARGET = 0x4000_2800


@pytest.mark.feature('BPU-ITTAGE-020')
async def test_late_feedback_does_not_learn_an_unpublished_ittage_original(
    bpu_agent, bpu_sc_output, request,
):
    coverage = LateSourceCoverage()
    evidence = dict(late_pc=hex(LATE_PC), target=hex(TARGET))
    try:
        await bpu_agent.check_unpublished_ittage(pc=LATE_PC, position=POSITION, target=TARGET,
                                               coverage=coverage, evidence=evidence)
    except Exception as error:
        evidence['failure'] = str(error)
        request.node.user_properties.append(
            ('bpu_late_source_qualification', json.dumps(evidence, ensure_ascii=False))
        )
        raise
    finally:
        coverage.write(bpu_sc_output)
