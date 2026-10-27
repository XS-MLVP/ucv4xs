"""Wrong-path operations lose their owners even when public keys alias."""
import pytest

from bpuverify.ras.model.semantic import Events,RasReference,Recovery,Retirement


ADDRESS = 0x80030020


def action(model,kind,address=None):
    before = dict(model.projection)
    model.advance(Events(kind,address))
    model.advance()
    return before


def retire(model,before,kind):
    model.advance(Events(retirement=Retirement(before['group'],before['calls'],kind)))
    model.advance()
    model.advance()


@pytest.mark.parametrize('calls',(8,9))
@pytest.mark.parametrize('committed',(False,True))
def test_restored_return_has_one_owner_and_later_returns_keep_their_own_prefix(calls,committed):
    model = RasReference()
    sources = [action(model,2,ADDRESS) for _ in range(calls)]
    if committed:
        for before in sources:retire(model,before,2)
    prefix = dict(model.projection)
    old = [action(model,1) for _ in range(3)]
    old_owners = [op.sequence for op in model.operations if op.action==1]
    assert len(old_owners)==3
    assert len(model.program.frames)-1==calls-3
    model.advance(Events(recovery=Recovery(prefix['group'],prefix['calls'],prefix['repeat'],1)))
    model.advance()
    assert len(model.program.frames)-1==calls-1
    assert model.projection==dict(top=ADDRESS//2,group=1,repeat=calls-2,calls=calls)
    assert all(op.sequence not in old_owners for op in model.operations)
    return_owners = [op for op in model.operations if op.action==1]
    assert len(return_owners)==1 and return_owners[0].before.head.repeat==prefix['repeat']
    if not committed:
        for before in sources:retire(model,before,2)
    retire(model,prefix,1)
    for count in (2,3,4):
        before = action(model,1)
        retire(model,before,1)
        assert model.projection==dict(top=ADDRESS//2,group=1,repeat=calls-count-1,calls=calls)
        assert model.committed[1].repeat==calls-count-1
    assert model.retirements==calls+4
    assert not model.operations


@pytest.mark.parametrize('kind',(0,1,2,3))
def test_recovery_discards_younger_calls_before_accepting_its_optional_redo(kind):
    model = RasReference()
    action(model,2,0x1000)
    prefix = dict(model.projection)
    old = [action(model,2,address) for address in (0x2000,0x3000)]
    old_owners = {op.sequence for op in model.operations[1:]}
    model.advance(Events(recovery=Recovery(prefix['group'],prefix['calls'],prefix['repeat'],kind,
        0x4000 if kind&2 else None)))
    model.advance()
    assert all(op.sequence not in old_owners for op in model.operations)
    assert len(model.operations)==1+int(bool(kind))
    assert model.operations[0].before.calls==0
    if kind:
        assert model.operations[1].before.calls==1 and model.operations[1].action==kind
    with pytest.raises(AssertionError,match='owned speculative source'):
        model.advance(Events(retirement=Retirement(old[-1]['group'],old[-1]['calls'],2)))


def test_rejected_or_disabled_recovery_does_not_cancel_owners_early():
    model = RasReference()
    action(model,2,ADDRESS)
    before = tuple(model.operations)
    model.advance(Events(recovery=Recovery(0,0,0)))
    assert tuple(model.operations)==before  # Not yet the registered effect.
    model.advance(Events(enabled=False))
    assert tuple(model.operations)==before


def test_reset_clears_semantic_frontiers_and_live_operation_owners():
    model = RasReference()
    action(model,2,ADDRESS)
    model.advance(Events(reset=True))
    assert model.accepted_sequence==0 and not model.operations
    assert model.checkpoint_sequences=={(0,0,0):0}


def test_checkpoint_eviction_expires_its_frontier_in_lockstep():
    model = RasReference()
    # Exercise the bounded ownership index directly; no fake DUT coverage.
    from bpuverify.ras.model.semantic import Frame,Program
    for index in range(140):
        model._remember(Program((Frame(group=index//32,repeat=0),),index%32))
    assert model.checkpoints.keys()==model.checkpoint_sequences.keys()
    assert len(model.checkpoints)==128
