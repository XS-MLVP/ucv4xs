"""Use the existing Main model to derive the true miss authority contract."""
from copy import deepcopy
from dataclasses import replace
import pytest
from bpuverify.mbtb.model.semantic import Source,MbtbReference,Events,Feedback,Branch,tag
from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.model.main_service import counter_payload
from bpuverify.bpu.model.miss_authority import Program,PC,FOREIGN_PC,RESIDENT_POSITION,STREAM_PC



def lookup(model, pc=PC):
    event = Events(pc, select=True, advance=True, consume=True)
    model.advance(event)
    model.advance(event)
    return model.frame


def feedback(frame, *, position=3, kind=1, action=0, target=PC + 0x234, taken=True, mispredict=True):
    sources = tuple(tuple(Source(entry.valid and entry.tag == tag(read.pc),
        read.ordinal * 16 + entry.position, entry.kind, entry.action, counter)
        for entry, counter in zip(read.entries, read.counters, strict=True)) + (Source(),) for read in frame.banks)
    return Feedback((frame.pc, (frame.pc // 16 + 1) * 16), sources,
                    (Branch(target, taken, position, kind, action, mispredict),))


def learn(model, request):
    model.advance(Events(feedback=request))
    for _ in range(5):
        model.advance()



def derive(p,*,canonical=False):
    model=MbtbReference()
    learn(model,feedback(lookup(model),position=RESIDENT_POSITION,target=STREAM_PC))
    before=deepcopy(model.counters)
    frame=lookup(model,FOREIGN_PC)
    original=deepcopy(frame)
    tx=feedback(frame,position=p.position,target=STREAM_PC,taken=bool(p.taken),mispredict=p.allocate)
    assert not any(s.hit for row in tx.sources for s in row)
    assert tx.sources[0][3].position==RESIDENT_POSITION and tx.sources[0][3].counter==2
    if canonical:tx=replace(tx,sources=source_entries(frame))
    model.advance(Events(feedback=tx))
    patch=model.direction_proposals().get((0,0))
    assert (None if patch is None else counter_payload(patch))==p.direction
    for _ in range(5):model.advance()
    assert lookup(model).values()['3.counter']==2
    assert model.counters[0,0,16,3]==before[0,0,16,3]==2
    if p.allocate:
        assert lookup(model,FOREIGN_PC).values()['2.counter']==2
    else:assert model.counters==before
    assert frame==original
    return model.counters


@pytest.mark.parametrize('allocate',(False,True))
@pytest.mark.parametrize('same_position',(False,True))
def test_literal_and_canonical_unhit_payloads_have_identical_qualified_effects(allocate,same_position):
    p=Program(allocate,same_position)
    assert derive(p)==derive(p,canonical=True)


@pytest.mark.parametrize('position',(RESIDENT_POSITION,6))
@pytest.mark.parametrize('kind',(0,1,2,3))
@pytest.mark.parametrize('counter',(0,3))
def test_arbitrary_unqualified_source_payload_cannot_grant_direction_update(position,kind,counter):
    model=MbtbReference()
    learn(model,feedback(lookup(model),position=RESIDENT_POSITION,target=STREAM_PC))
    before=deepcopy(model.counters)
    miss=feedback(lookup(model,FOREIGN_PC),position=RESIDENT_POSITION,taken=False,mispredict=False)
    miss=replace(miss,sources=tuple(tuple(Source(False,position,kind,0,counter) for _ in row) for row in miss.sources))
    learn(model,miss)
    assert model.counters==before
