"""Composed BPU: late feedback without an original ITTAGE snapshot must not learn."""
import json

import pytest

from suites.frontend.bpu.bpu.coverage.late_source import LateSourceCoverage
from suites.frontend.bpu.bpu.env.indirect_learning import indirect_program
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback

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
        async with indirect_program(bpu_agent, LATE_PC) as env:
            agent = env.agent
            checker = env.checker

            # 1. A real original is predicted while ITTAGE service is off.
            await agent.configure_predictors(ittage=False, settle=True)
            original = await env.capture_source(LATE_PC)
            original_meta = original.meta.resolve['ittage']
            assert original_meta['valid'] == 0
            evidence['original'] = dict(valid=original_meta['valid'],
                                        provider=original_meta['provider'],
                                        allocate=original_meta['allocate'])
            coverage.record('reached', 'unpublished-original-observed',
                            valid=original_meta['valid'])
            coverage.record('checked', 'unpublished-original-observed')

            # 2. Re-enable ITTAGE and take a genuine fresh snapshot.
            await agent.configure_predictors(ittage=True, settle=True)
            fresh = await env.capture_source(LATE_PC)
            fresh_meta = fresh.meta.resolve['ittage']
            assert fresh_meta['valid'] == 1
            evidence['fresh'] = dict(valid=fresh_meta['valid'],
                                     provider=fresh_meta['provider'],
                                     allocate=fresh_meta['allocate'])

            # 3. The original block's real taken indirect outcome arrives
            #    while ITTAGE is enabled. The ITTAGE master valid bit says the
            #    original had no snapshot; the branch is still a real input.
            coverage.record('reached', 'late-feedback-does-not-learn-ittage',
                            valid=original_meta['valid'])
            await env.resolve(
                original,
                BpuBranchFeedback(POSITION, TARGET, branch_type=3, taken=1, mispredict=1),
            )

            # 4. A fresh consumer must remain cold for ITTAGE. The token also
            #    compares Main and history metadata, so the rest of the
            #    composed source must still be consistent before ITTAGE is
            #    allowed to fail.
            coverage.record('reached', 'fresh-consumer-remains-cold')
            final = await env.capture_source(LATE_PC)
            final_meta = final.meta.resolve['ittage']
            assert final_meta['valid'] == 1
            assert final_meta['provider']['valid'] == 0, (
                'an unpublished original must not create an ITTAGE provider'
            )
            coverage.record('checked', 'fresh-consumer-remains-cold')
            evidence['final'] = dict(valid=final_meta['valid'],
                                     provider=final_meta['provider'],
                                     allocate=final_meta['allocate'])
            checker.raise_failure()
    except Exception as error:
        evidence['failure'] = str(error)
        request.node.user_properties.append(
            ('bpu_late_source_qualification', json.dumps(evidence, ensure_ascii=False))
        )
        raise
    finally:
        coverage.write(bpu_sc_output)
