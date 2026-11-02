"""Actual inputs must match the declared IDs, not a self-consistent wrong wire."""
from copy import deepcopy
import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.mbtb.checker.training_inputs import TrainingInputs
from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining,MbtbBranchFeedback
from suites.frontend.bpu.mbtb.driver.feedback import expected_mbtb_feedback


def transaction():
    meta=tuple(tuple(dict(rawHit=0,position=0,counter_value=0,attribute=dict(branchType=0,rasAction=0))
        for _ in range(4)) for _ in range(2))
    return MbtbBatchTraining(0x80000000,meta,(MbtbBranchFeedback(0x80002340,1,5,3,mispredict=1),None))


def observe(inputs,tick=2,**changes):
    values=dict(reset=False,ready=True,enabled=True,feedback=expected_mbtb_feedback(transaction()))
    values.update(changes);inputs.observe(tick,**values)


def test_equal_payloads_have_distinct_input_ids_and_complete_exactly_once():
    inputs=TrainingInputs();ids=inputs.plan((transaction(),transaction()));assert ids==(1,2)
    observe(inputs);observe(inputs,4)
    with pytest.raises(AssertionError):inputs.finish()
    inputs.drained(6,ids);assert [row.uid for row in inputs.finish()]==[1,2]


@pytest.mark.parametrize('field',('target','taken','position','branch_type','ras_action','mispredict'))
def test_self_consistent_wrong_wire_branch_cannot_redefine_the_planned_input(field):
    inputs=TrainingInputs();inputs.plan((transaction(),));wrong=deepcopy(expected_mbtb_feedback(transaction()))
    wrong['resolved'][0][field]^=1
    with pytest.raises(ScoreboardMismatch) as caught:observe(inputs,feedback=wrong)
    assert inputs.rows[0].state=='planned'
    with pytest.raises(ScoreboardMismatch) as later:inputs.finish()
    assert later.value is caught.value


@pytest.mark.parametrize('field',('rawHit','position','counter_value','branchType','rasAction'))
def test_all_four_way_metadata_fields_are_compared_even_when_the_source_does_not_hit(field):
    inputs=TrainingInputs();inputs.plan((transaction(),));wrong=deepcopy(expected_mbtb_feedback(transaction()))
    selected=wrong['meta_entries'][1][3]
    if field in ('branchType','rasAction'):selected=selected['attribute']
    selected[field]^=1
    with pytest.raises(ScoreboardMismatch):observe(inputs,feedback=wrong)


@pytest.mark.parametrize('field',('pc','next_pc','ready','sparse-valid','missing-metadata'))
def test_complete_input_schema_and_sparse_valid_positions_are_not_lost_in_semantic_decode(field):
    inputs=TrainingInputs();inputs.plan((transaction(),));wrong=deepcopy(expected_mbtb_feedback(transaction()))
    if field in ('pc','next_pc','ready'):wrong[field]^=1
    elif field=='sparse-valid':wrong['resolved']=(None,wrong['resolved'][0],*wrong['resolved'][2:])
    else:wrong['meta_entries']=wrong['meta_entries'][:1]
    with pytest.raises(ScoreboardMismatch):observe(inputs,feedback=wrong)


@pytest.mark.parametrize('gate,state',(('reset','reset-filtered'),('ready','initialization-filtered'),('enabled','disabled-filtered')))
def test_real_sampled_gate_classifies_offered_not_accepted_inputs(gate,state):
    inputs=TrainingInputs();inputs.plan((transaction(),));observe(inputs,**{gate:gate=='reset'})
    row,=inputs.finish();assert row.state==state and row.offer_tick==2


def test_reset_cancels_only_the_named_accepted_lifetime_and_never_reuses_its_id():
    inputs=TrainingInputs();inputs.plan((transaction(),));observe(inputs)
    observe(inputs,4,reset=True,feedback=None)
    assert inputs.finish()[0].state=='reset-cancelled'
    ids=inputs.plan((transaction(),));assert ids==(2,)
    observe(inputs,6);inputs.drained(8,ids)
    first,second=inputs.finish();assert first.offer_epoch==0 and second.offer_epoch==1


@pytest.mark.parametrize('fault',('wrong-uid','duplicate','missing','changed-state','unknown-row'))
def test_matching_counts_do_not_replace_the_exact_terminal_uid_history(fault):
    inputs=TrainingInputs();ids=inputs.plan((transaction(),));observe(inputs);inputs.drained(4,ids)
    if fault=='wrong-uid':inputs._terminals[0]=(99,'local-drained',4)
    elif fault=='duplicate':inputs._terminals.append(inputs._terminals[0])
    elif fault=='missing':inputs._terminals.clear()
    elif fault=='changed-state':inputs._terminals[0]=(1,'reset-cancelled',4)
    else:inputs._rows[99]=inputs._rows[1]
    with pytest.raises(AssertionError):inputs.finish()


def test_unplanned_or_duplicate_physical_offer_is_not_a_new_inferred_uid():
    inputs=TrainingInputs()
    with pytest.raises(AssertionError):observe(inputs)
    inputs=TrainingInputs();ids=inputs.plan((transaction(),));observe(inputs);inputs.drained(4,ids)
    with pytest.raises(AssertionError):observe(inputs,6)


def test_cancel_before_actual_offer_is_not_a_fake_acceptance_or_completion():
    inputs=TrainingInputs();ids=inputs.plan((transaction(),));inputs.cancel_inputs(ids,at=0)
    with pytest.raises(AssertionError):inputs.finish()
    observe(inputs,2,feedback=None)
    row,=inputs.finish();assert row.state=='cancelled-before-offer' and row.offer_tick is None


def test_cancel_does_not_erase_an_already_present_but_delayed_input_observation():
    inputs=TrainingInputs();ids=inputs.plan((transaction(),transaction()));inputs.cancel_inputs(ids,at=2)
    observe(inputs,2);observe(inputs,4,feedback=None)
    with pytest.raises(AssertionError):inputs.finish()
    inputs.drained(6,(ids[0],))
    assert [row.state for row in inputs.finish()]==['local-drained','cancelled-before-offer']


def test_a_later_physical_offer_cannot_reuse_a_cancelled_equal_payload_plan():
    inputs=TrainingInputs();ids=inputs.plan((transaction(),transaction()));inputs.cancel_inputs(ids,at=2)
    observe(inputs,2)
    with pytest.raises(AssertionError,match='no input-established UID'):observe(inputs,4)


def test_invalid_plan_is_rejected_atomically_before_allocating_any_input_identity():
    inputs=TrainingInputs()
    with pytest.raises(ValueError):inputs.plan((transaction(),None))
    assert inputs.rows==() and inputs.plan((transaction(),))==(1,)
