"""Exact prediction lifetimes must not collapse into equal RAS pointer words."""
from copy import deepcopy
from dataclasses import replace

import pytest

from bpuverify.ras.model.semantic import Events, Original, RasReference, Recovery, Retirement


def observe(model, action=0, address=None):
    source = model.capture_original()
    model.advance(Events(action=action,address=address,origin=source))
    return source


def recover(source, action=0, address=None):
    return Recovery(*source.program.redirect_key(),action,address,origin=source)


def retire(source, action):
    return Retirement(*source.program.commit_key(),action,origin=source)


def fingerprint(model):
    return (deepcopy(model.state()),tuple(model.operations),dict(model.checkpoints),
            dict(model.checkpoint_sequences),dict(model._originals),
            dict(model._original_operations),set(model._retired_originals),model.pending_retirement_origin)


@pytest.mark.parametrize('fault', ('copy','foreign','released','reset','fabricated'))
@pytest.mark.parametrize('operation', ('require','recovery','retirement','speculation'))
def test_invalid_originals_are_rejected_without_partial_state_change(fault, operation):
    m = RasReference()
    source = observe(m,2,0x40001000)
    if fault == 'copy':
        bad = replace(source)
    elif fault == 'foreign':
        bad = observe(RasReference(),2,0x40001000)
    elif fault == 'released':
        bad = source
        m.release_original(source)
    elif fault == 'reset':
        bad = source
        m.advance(Events(reset=True))
    else:
        bad = Original(source.epoch,source.serial,source.program,source.frontier)
    before = fingerprint(m)
    with pytest.raises(ValueError):
        if operation == 'require':
            m.require_original(bad)
        elif operation == 'recovery':
            m.advance(Events(recovery=recover(bad)))
        elif operation == 'retirement':
            m.advance(Events(retirement=retire(bad,2)))
        else:
            m.advance(Events(action=2,address=0x40002000,origin=bad))
    assert fingerprint(m) == before


def test_equal_encoded_neutral_and_call_originals_cannot_borrow_one_anothers_address():
    m = RasReference()
    neutral = observe(m)
    call = observe(m,2,0x40001000)
    assert neutral is not call and neutral.program is call.program
    assert neutral.program.redirect_key() == call.program.redirect_key()
    before = fingerprint(m)
    with pytest.raises(ValueError,match='borrowed'):
        m.advance(Events(retirement=retire(neutral,2)))
    assert fingerprint(m) == before
    m.advance(Events(retirement=retire(call,2)))
    m.advance()
    assert m.committed[1].address == 0x40001000 and m.retirements == 1


def test_exact_recovery_uses_its_saved_frontier_even_when_a_numeric_entry_was_overwritten():
    m = RasReference()
    observe(m,2,0x40001000)
    original = observe(m)
    younger = observe(m,2,0x40002000)
    # Do not use corrupted input fields: the numeric compatibility index is
    # deliberately wrong to prove the typed API uses its own immutable source.
    key = original.program.redirect_key()
    m.checkpoints[key] = m.program
    m.checkpoint_sequences[key] = m.accepted_sequence
    m.advance(Events(recovery=recover(original)))
    with pytest.raises(ValueError,match='pending'):
        m.release_original(original)
    m.advance()
    assert m.program == original.program and m.projection['top'] == 0x40001000//2
    before = fingerprint(m)
    with pytest.raises(ValueError,match='cancelled'):
        m.advance(Events(retirement=retire(younger,2)))
    assert fingerprint(m) == before


@pytest.mark.parametrize('action', range(4))
def test_recovery_redo_and_later_retirement_share_the_exact_original(action):
    m = RasReference()
    observe(m,2,0x40001000)
    source = observe(m,2,0x40002000)
    observe(m,2,0x40009000)
    address = 0x40003000 if action & 2 else None
    m.advance(Events(recovery=recover(source,action,address)))
    m.advance()
    assert m.program == m._apply(source.program,action,address)
    m.advance(Events(retirement=retire(source,action)))
    with pytest.raises(ValueError,match='pending'):
        m.release_original(source)
    m.advance()
    assert m.retirements == 1
    before = fingerprint(m)
    with pytest.raises(ValueError,match='twice'):
        m.advance(Events(retirement=retire(source,action)))
    assert fingerprint(m) == before
    m.release_original(source)


@pytest.mark.parametrize('kind', ('recovery','retirement'))
@pytest.mark.parametrize('field', ('group','calls'))
def test_compatible_numeric_fields_still_must_belong_to_the_typed_original(kind,field):
    m = RasReference()
    source = observe(m,2,0x40001000)
    request = recover(source) if kind == 'recovery' else retire(source,2)
    request = replace(request,**{field:getattr(request,field)+1})
    before = fingerprint(m)
    with pytest.raises(ValueError,match='fields'):
        m.advance(Events(**{kind:request}))
    assert fingerprint(m) == before


def test_an_unpublished_capture_cannot_restore_or_retire_an_event_that_never_happened():
    m = RasReference()
    source = m.capture_original()
    before = fingerprint(m)
    with pytest.raises(ValueError,match='observed'):
        m.advance(Events(recovery=recover(source)))
    assert fingerprint(m) == before
    with pytest.raises(ValueError,match='observed'):
        m.advance(Events(retirement=retire(source,0)))
    assert fingerprint(m) == before


@pytest.mark.parametrize('fault', ('bad-call-address','bad-action','bad-retirement-after-valid-call'))
def test_invalid_semantic_commands_are_atomic_even_after_other_work_was_possible(fault):
    m = RasReference()
    source = observe(m,2,0x40001000)
    before = fingerprint(m)
    if fault == 'bad-call-address':
        event = Events(action=2,address=3)
    elif fault == 'bad-action':
        event = Events(action=4)
    else:
        event = Events(action=2,address=0x40002000,retirement=Retirement(7,23,2))
    with pytest.raises((ValueError,AssertionError)):
        m.advance(event)
    assert fingerprint(m) == before
