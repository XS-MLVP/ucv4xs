"""Late feedback may only teach from the snapshot its original prediction published."""
import json

import pytest

from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.ittage.case.definitions import PC
from suites.frontend.bpu.ittage.case.definitions import POSITION
from suites.frontend.bpu.ittage.case.definitions import TARGET_A
from suites.frontend.bpu.ittage.coverage.late_source import LateSourceCoverage
from suites.frontend.bpu.ittage.transaction.types import IttageTraining

UNSERVED_PC, CONTROL_PC = PC, PC + 0x20


@pytest.mark.feature('BPU-ITTAGE-020')
async def test_late_feedback_for_an_unpublished_original_does_not_create_a_target(
    ittage_agent, request,
):
    """A disabled original has no ITTAGE snapshot; its residue is not a source.

    The control prediction is served and learns normally. The observed late
    prediction is made while ITTAGE is enabled again, so this is not the
    existing "feedback arriving while disabled" gate: the only missing
    qualification is that the *original* query never published a snapshot.
    """

    coverage = LateSourceCoverage()
    evidence = dict(control_pc=hex(CONTROL_PC), late_pc=hex(UNSERVED_PC))
    try:
        await ittage_agent.reset()

        # Establish the last enabled service at a different PC. When the next
        # query is taken while disabled, its subfields retain this unrelated
        # query's values; they do not belong to the disabled original.
        served_control_anchor = await ittage_agent.predict(CONTROL_PC)
        assert served_control_anchor.meta['valid'] == 1
        await ittage_agent.set_enabled(False)
        unpublished = await ittage_agent.predict(UNSERVED_PC)
        assert unpublished.meta['valid'] == 0
        evidence['unpublished_meta'] = unpublished.meta

        await ittage_agent.set_enabled(True)
        fresh_unserved = await ittage_agent.predict(UNSERVED_PC)
        fresh_control = await ittage_agent.predict(CONTROL_PC)
        assert fresh_unserved.meta['valid'] == 1 and fresh_unserved.hit == 0
        assert fresh_control.meta['valid'] == 1 and fresh_control.hit == 0
        evidence['fresh_unserved_allocate'] = fresh_unserved.meta['allocate']
        evidence['fresh_control_allocate'] = fresh_control.meta['allocate']
        coverage.record(
            'reached', 'unpublished-original-observed',
            unpublished_valid=unpublished.meta['valid'],
            unpublished_allocate=unpublished.meta['allocate'],
            fresh_unserved_allocate=fresh_unserved.meta['allocate'],
        )
        coverage.record('checked', 'unpublished-original-observed')

        # Served control: the same feedback shape, but its original snapshot
        # was published. It must learn the complete target.
        coverage.record('reached', 'served-control-learns')
        await ittage_agent.train(
            IttageTraining(CONTROL_PC, POSITION, TARGET_A, fresh_control.meta, 1)
        )
        control = await ittage_agent.predict(CONTROL_PC)
        assert (control.hit, control.target) == (1, TARGET_A)
        evidence['served_control'] = dict(
            hit=control.hit, target=hex(control.target),
            provider=control.meta['provider'], target_field=control.meta['providerTarget_addr'],
        )
        coverage.record('checked', 'served-control-learns',
                        target=hex(control.target))

        # Late feedback for the unpublished original, accepted while ITTAGE
        # is enabled. The ownership rule says the component has no snapshot
        # and therefore must not create a target.
        coverage.record('reached', 'late-feedback-does-not-learn',
                        **{'allocate_residue': unpublished.meta['allocate'],
                           'enabled_at_feedback': True})
        await ittage_agent.train(
            IttageTraining(UNSERVED_PC, POSITION, TARGET_A, unpublished.meta, 1)
        )
        after = await ittage_agent.predict(UNSERVED_PC)
        assert after.hit == 0, 'an unpublished original must not create a target'
        coverage.record('checked', 'late-feedback-does-not-learn')
        evidence['late_consumer'] = dict(hit=after.hit, meta=after.meta)
    except Exception as error:
        evidence['failure'] = str(error)
        request.node.user_properties.append(
            ('ittage_late_source_qualification', json.dumps(evidence, ensure_ascii=False))
        )
        raise
    finally:
        coverage.write(REPO_ROOT)
