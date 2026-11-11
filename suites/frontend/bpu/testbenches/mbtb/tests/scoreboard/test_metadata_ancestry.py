"""Ancestry is input identity, not a payload-based lookup or branch oracle."""
from copy import deepcopy
from dataclasses import replace
import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.testbenches.mbtb.checker.lookup_inputs import LookupInputs
from suites.frontend.bpu.testbenches.mbtb.checker.training_inputs import TrainingInputs
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Events
from suites.frontend.bpu.testbenches.mbtb.transactions.metadata import declared_metadata
from suites.frontend.bpu.testbenches.mbtb.transactions.metadata import freeze_metadata
from suites.frontend.bpu.testbenches.mbtb.transactions.metadata import metadata_origin
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbBatchTraining
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbBranchFeedback

PC=0x80000000


def metadata():
    return tuple(tuple(dict(rawHit=0,position=0,counter_value=0,attribute=dict(branchType=0,rasAction=0))
        for _ in range(4))+(dict(rawHit=0,position=0,counter_value=0),) for _ in range(2))


def source():
    from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbLookup
    inputs=LookupInputs();inputs.plan(10,MbtbLookup(PC));inputs.launched(10,2)
    inputs.observe(2,Events(select=True,pc=PC));inputs.stage(10,'advance')
    inputs.observe(4,Events(advance=True));inputs.observe_output(6)
    origin=inputs.source_at(6);values=freeze_metadata(metadata(),origin=origin)
    inputs.register_source(origin,values)
    return inputs,values


def transaction(values,pc=PC):
    return MbtbBatchTraining(pc,values,(MbtbBranchFeedback(PC+0x2340,1,5,3,mispredict=1),))


def test_mutable_diagnostic_copy_preserves_its_immutable_source_declaration():
    _,values=source();copied=deepcopy(values)
    assert metadata_origin(copied)==metadata_origin(values)
    copied[0][0]['counter_value']=1
    assert values[0][0]['counter_value']==0
    with pytest.raises(AttributeError):copied[0][0].origin=None


@pytest.mark.parametrize('fault',('counter','position','kind','rawHit','pc','epoch','uid','offer','response',
    'victim-rawHit','victim-position','victim-counter'))
def test_an_equal_or_edited_payload_cannot_redefine_a_known_source(fault):
    inputs,values=source();origin=metadata_origin(values);copied=deepcopy(values);pc=PC
    if fault in ('counter','position','rawHit'):
        copied[0][0][{'counter':'counter_value','position':'position','rawHit':'rawHit'}[fault]]^=1
    elif fault=='kind':copied[1][3]['attribute']['branchType']=1
    elif fault.startswith('victim-'):
        copied[0][4][{'victim-rawHit':'rawHit','victim-position':'position','victim-counter':'counter_value'}[fault]]^=1
    elif fault=='pc':pc^=0x80
    else:
        name={'epoch':'epoch','uid':'uid','offer':'offer_tick','response':'response_tick'}[fault]
        copied=freeze_metadata(copied,origin=replace(origin,**{name:getattr(origin,name)+1}))
    with pytest.raises(ScoreboardMismatch):inputs.validate_training_source(transaction(copied,pc))


def test_late_validation_in_a_burst_cannot_allocate_or_partially_emit_earlier_inputs():
    inputs,values=source();ledger=TrainingInputs(validate_source=inputs.validate_training_source)
    with pytest.raises(ScoreboardMismatch):ledger.plan((transaction(values),transaction(values,PC^0x80)))
    assert ledger.rows==()
    assert ledger.plan((transaction(values),))==(1,)


def test_reset_rejects_old_epoch_metadata_even_if_the_new_pc_and_bits_are_identical():
    inputs,values=source();inputs.observe(8,Events(reset=True))
    with pytest.raises(ScoreboardMismatch):inputs.validate_training_source(transaction(values))


def test_explicit_port_characterization_edit_is_legal_but_never_gets_lookup_credit():
    inputs,values=source();copied=deepcopy(values);copied[0][0]['counter_value']=1
    with pytest.raises(ScoreboardMismatch):inputs.validate_training_source(transaction(copied))
    declared=declared_metadata(copied,reason='isolated stale counter/owner port characterization')
    assert metadata_origin(declared) is None
    inputs.validate_training_source(transaction(declared))
    ledger=TrainingInputs(validate_source=inputs.validate_training_source);ledger.plan((transaction(declared),))
    receipt,=ledger.receipt()
    assert receipt['metadata_scope']=='declared-upstream-input' and receipt['source'] is None
    assert receipt['declared_reasons']==('isolated stale counter/owner port characterization',)


def test_external_equal_bits_cannot_inherit_an_origin_by_payload_matching():
    inputs,_=source();external=freeze_metadata(metadata());inputs.validate_training_source(transaction(external))
    assert metadata_origin(external) is None


def test_dropping_only_one_ancestor_fragment_is_rejected_instead_of_downgrading_the_whole_plan():
    _,values=source();mixed=[list(row) for row in deepcopy(values)];mixed[0][0]=metadata()[0][0]
    with pytest.raises(ValueError,match='mix lookup ancestors'):transaction(mixed)


def test_explicit_characterization_detachment_requires_a_nonempty_reason():
    with pytest.raises(ValueError,match='reason'):declared_metadata(metadata(),reason=' ')
