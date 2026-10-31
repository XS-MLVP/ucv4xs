"""Boundary-adapter controls; synthetic events do not obtain hardware credit."""
from types import SimpleNamespace as N
import pytest
from suites.frontend.bpu.bpu.monitor.window_lifetime import AcceptedWindowEvents
from suites.frontend.bpu.bpu.model.window_lifetime import LifetimeError


def token(sequence, pc=0x40000800):
    return N(sequence=sequence, pc=pc)


def cycle(*, first=None, second=None, third=None, accept=False, flush=False,
          middle=False, final=False, publish=False):
    return N(tokens=(first, second, third), fires=(False, accept, False, False),
        flushes=(flush, final, False), middle_repair=middle, final_repair=final,
        metadata=third if publish else None)


def metadata(t):
    return dict(valid=1, pc=t.pc, history={'bits': 0}, main=({'hit': 0},))


def admit(m, t, tick):
    m.observe(cycle(first=t, accept=True), tick, {})


def publish(m, t, tick):
    m.observe(cycle(third=t, publish=True), tick, metadata(t))


def test_all_accepted_occurrences_count_even_if_a_case_selects_only_one_receipt():
    m=AcceptedWindowEvents(3)
    sources=[token(i) for i in range(3)]
    for i,t in enumerate(sources):admit(m,t,10+2*i)
    assert m.counts['S1-admission']==3 and m.peak==3
    before=m.ledger.state()
    with pytest.raises(LifetimeError,match='full window'):admit(m,token(3),16)
    assert m.ledger.state()==before


def test_a_firing_but_flushed_S1_is_not_a_new_window():
    m=AcceptedWindowEvents(1)
    m.observe(cycle(first=token(0),accept=True,flush=True),10,{})
    assert not m.windows and not m.ledger.active


@pytest.mark.parametrize('stage',('S2','S3'))
def test_internal_correction_keeps_its_owner_and_drops_only_younger_windows(stage):
    m=AcceptedWindowEvents(4)
    a,b,c=[token(i) for i in range(3)]
    for i,t in enumerate((a,b,c)):admit(m,t,10+2*i)
    kwargs=dict(second=b,middle=True) if stage=='S2' else dict(third=b,final=True)
    m.observe(cycle(**kwargs),20,{})
    assert m.ledger.active==[m.owner(a),m.owner(b)]
    assert m.redirects[-1]==dict(tick=20,kind=stage,owner=1,discarded=(2,))
    admit(m,token(3),22)
    assert m.owner(token(3)).slot==m.owner(c).slot


def test_S3_correction_wins_over_younger_S2_correction():
    m=AcceptedWindowEvents(3)
    a,b,c=[token(i) for i in range(3)]
    for i,t in enumerate((a,b,c)):admit(m,t,10+2*i)
    m.observe(cycle(first=c,second=b,third=a,middle=True,final=True,accept=True,flush=True),20,{})
    assert m.ledger.active==[m.owner(a)]
    assert m.redirects[-1]['kind']=='S3'


def test_external_redirect_wins_over_all_internal_corrections_and_old_path_metadata():
    m=AcceptedWindowEvents(3)
    a,b,c=[token(i) for i in range(3)]
    for i,t in enumerate((a,b,c)):admit(m,t,10+2*i)
    m.observe(cycle(first=c,second=b,third=a,middle=True,final=True,publish=True),20,
        metadata(a),redirect_owner=a)
    assert m.ledger.active==[m.owner(a)] and not m.published_at
    assert m.redirects[-1]['kind']=='external'


@pytest.mark.parametrize('operation',('metadata','S2','S3','external'))
def test_missing_original_acceptance_cannot_be_reconstructed_from_current_stage_wires(operation):
    m=AcceptedWindowEvents(2)
    t=token(0)
    with pytest.raises(AssertionError,match='previously accepted'):
        if operation=='metadata':publish(m,t,10)
        elif operation=='external':m.observe(cycle(),10,{},redirect_owner=t)
        else:m.observe(cycle(second=t,middle=True) if operation=='S2' else cycle(third=t,final=True),10,{})


def test_selected_receipt_requires_both_actual_acceptance_and_publication_ticks():
    m=AcceptedWindowEvents(2);t=token(0)
    admit(m,t,10);publish(m,t,14)
    good=N(prediction_tick=10,meta_tick=14,prediction=N(start_pc=t.pc))
    assert m.receipt(t,good) is m.owner(t)
    for bad in (N(prediction_tick=12,meta_tick=14,prediction=good.prediction),
                N(prediction_tick=10,meta_tick=16,prediction=good.prediction),
                N(prediction_tick=10,meta_tick=14,prediction=N(start_pc=t.pc+2))):
        with pytest.raises(AssertionError,match='boundaries'):m.receipt(t,bad)


def test_equal_PC_and_metadata_do_not_make_a_flushed_receipt_eligible_again():
    m=AcceptedWindowEvents(3);a,b=token(0),token(1)
    admit(m,a,10);publish(m,a,14)
    admit(m,b,16);publish(m,b,20)
    assert m.ledger.metadata[m.owner(a).sequence]==m.ledger.metadata[m.owner(b).sequence]
    m.observe(cycle(),22,{},redirect_owner=a)
    receipt=N(prediction_tick=16,meta_tick=20,prediction=N(start_pc=b.pc))
    assert m.receipt(b,receipt) is m.owner(b)
    with pytest.raises(LifetimeError,match='flushed'):m.ledger.live(m.receipt(b,receipt))


def test_reset_does_not_borrow_an_old_S1_or_publication_association():
    m=AcceptedWindowEvents(2);t=token(0)
    admit(m,t,10);publish(m,t,14)
    m.reset()
    with pytest.raises(AssertionError,match='previously accepted'):m.owner(t)
    assert not m.accepted_at and not m.published_at and not m.ledger.active


def test_stage_PC_change_is_rejected_instead_of_rebinding_the_original():
    m=AcceptedWindowEvents(2);admit(m,token(0),10)
    with pytest.raises(AssertionError,match='changed'):m.owner(token(0,pc=0x40000900))


def test_repeated_S1_acceptance_is_not_a_second_occurrence():
    m=AcceptedWindowEvents(2);t=token(0);admit(m,t,10)
    with pytest.raises(AssertionError,match='fresh original'):admit(m,t,12)


@pytest.mark.parametrize('field',('valid','pc'))
def test_metadata_requires_its_actual_valid_and_original_PC(field):
    m=AcceptedWindowEvents(2);t=token(0);admit(m,t,10)
    value=metadata(t);value[field]=0
    with pytest.raises(AssertionError,match='exact S3'):m.observe(cycle(third=t,publish=True),14,value)


def test_no_commit_is_inferred_when_all_accepted_sources_leave_the_BPU_pipeline():
    m=AcceptedWindowEvents(1);t=token(0);admit(m,t,10);publish(m,t,14)
    m.observe(cycle(),16,{})
    assert m.ledger.active==[m.owner(t)] and not m.ledger.accepting


def test_slot_reuse_can_replace_latest_reason_without_erasing_the_actual_original_flush_event():
    m=AcceptedWindowEvents(3);a,b,c=token(0),token(1),token(2)
    admit(m,a,10);publish(m,a,14)
    admit(m,b,16);publish(m,b,20)
    m.observe(cycle(),22,{},redirect_owner=a)
    assert m.redirects[-1]['discarded']==(1,)
    admit(m,c,24);publish(m,c,28)
    assert m.owner(b).slot==m.owner(c).slot
    with pytest.raises(LifetimeError,match='metadata position reused'):m.ledger.live(m.owner(b))
    assert m.redirects[-1]['discarded']==(1,)


def test_redirect_from_the_newer_actual_owner_preserves_the_older_unresolved_original():
    m=AcceptedWindowEvents(3);a,b,c=token(0),token(1),token(2)
    for i,t in enumerate((a,b,c)):admit(m,t,10+2*i)
    m.observe(cycle(),20,{},redirect_owner=b)
    m.ledger.live(m.owner(a));m.ledger.live(m.owner(b))
    assert m.redirects[-1]['discarded']==(2,)
