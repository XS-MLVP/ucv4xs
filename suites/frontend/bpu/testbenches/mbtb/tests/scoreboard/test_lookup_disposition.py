"""Protocol terminals cannot impersonate a functional response or ancestry."""
from dataclasses import replace
import pytest
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbLookupDisposition
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbPrediction
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbEntry
from suites.frontend.bpu.testbenches.mbtb.transactions.metadata import MetadataOrigin
from suites.frontend.bpu.testbenches.mbtb.transactions.metadata import freeze_metadata
from suites.frontend.bpu.testbenches.mbtb.checker.lookup_inputs import LookupInputs
from suites.frontend.bpu.testbenches.mbtb.checker.prediction import MbtbPredictionScoreboard
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbLookup
from types import SimpleNamespace


def preview():
    values=tuple(tuple(dict(rawHit=0,position=0,counter_value=0,
        **(dict(attribute=dict(branchType=0,rasAction=0)) if way<4 else {}))
        for way in range(5)) for _ in range(2))
    return MbtbPrediction((MbtbEntry(0,0,0,0,0,0),)*10,values)


def terminal():
    return MbtbLookupDisposition(1,'reset-cancelled',0,2,4,6,preview())


def test_terminal_identity_and_diagnostic_sample_are_immutable_but_not_a_response():
    value=terminal()
    assert value.receipt()==dict(uid=1,reason='reset-cancelled',epoch=0,offer_tick=2,terminal_tick=4,delivery_tick=6)
    with pytest.raises(AttributeError):value.uid=2
    with pytest.raises(TypeError):value.preview.meta_entries[0][0]['rawHit']=1
    assert not hasattr(value,'entries') and not hasattr(value,'meta_entries')


@pytest.mark.parametrize('field,value',(('uid',True),('epoch',-1),('offer_tick',5),
    ('terminal_tick',7),('delivery_tick',3),('reason','responded'),('reason',{}),('preview',object())))
def test_invalid_terminal_cannot_erase_its_protocol_boundary(field,value):
    with pytest.raises(ValueError):replace(terminal(),**{field:value})


def test_preview_cannot_carry_a_genuine_metadata_origin_from_another_lookup():
    value=preview();origin=MetadataOrigin(9,0,0x80000000,2,6)
    source=MbtbPrediction(value.entries,freeze_metadata(value.meta_entries,prediction=True,origin=origin))
    with pytest.raises(ValueError,match='genuine lookup metadata source'):replace(terminal(),preview=source)


def test_original_semantic_failure_is_not_replaced_by_a_missing_delivery_witness():
    primary=AssertionError('original independently checked hardware mismatch')
    inputs=LookupInputs();inputs.plan(1,MbtbLookup(0x80000000))
    def fail():raise primary
    reference=SimpleNamespace(raise_failure=fail,response_expected=lambda *_:None)
    board=MbtbPredictionScoreboard(inputs,reference,compare=lambda *_:None)
    context=SimpleNamespace(sequence_id=1,observed_event=SimpleNamespace(tick=6))
    with pytest.raises(AssertionError) as caught:
        board.check(expected=lambda _:None,actual=preview(),context=context)
    assert caught.value is primary
