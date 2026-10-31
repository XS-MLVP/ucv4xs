import pytest
from suites.frontend.bpu.abtb.model.state.counter import CounterReference
from suites.frontend.bpu.abtb.model.state.counter import index
from suites.frontend.bpu.abtb.model.state.counter import TRANSITIONS
from suites.frontend.bpu.abtb.model.state.counter import touch
from suites.frontend.bpu.abtb.model.state.counter import victim


def training(*,taken,position=3,entry_position=3,branch_type=1,hit=1,bank=0,set_index=5):
    return dict(pc=0x4000080a,target=0x40080000,taken=taken,position=position,
        branch_type=branch_type,ras_action=0,mispredict=1,
        meta=dict(valid=1,bankMask=1<<bank,setIdx=set_index,entries=[
            dict(hit=hit if way==0 else 0,position=entry_position,
                attribute=dict(branchType=branch_type,rasAction=0)) for way in range(4)]))


@pytest.mark.parametrize('bank',range(4))
@pytest.mark.parametrize('set_index',range(64))
@pytest.mark.parametrize('way',range(4))
def test_bijection_all_physical_cells(bank,set_index,way):
    assert index(bank,set_index,way)==bank*256+set_index*4+way


@pytest.mark.parametrize('old,taken,new',[(0,1,1),(1,1,2),(2,1,3),(3,1,3),
                                        (3,0,2),(2,0,1),(1,0,0),(0,0,0)])
def test_hand_calculated_saturation_and_one_cycle_delay(old,taken,new):
    ref=CounterReference()
    cell=index(0,5,0)
    ref.cells[cell]=old
    assert ref.advance(reset=0,accepted=training(taken=taken),writes=[])==[]
    assert ref.cells[cell]==old
    events=ref.advance(reset=0,accepted=None,writes=[])
    assert ref.cells[cell]==new and len(events)==1
    assert events[0]['transition'] in TRANSITIONS
    assert sum(value for i,value in enumerate(ref.cells) if i!=cell)==0


@pytest.mark.parametrize('old',range(4))
def test_counter_reset_has_priority_over_same_cell_decrease(old):
    ref=CounterReference()
    ref.cells[index(0,5,0)]=old
    ref.advance(reset=0,accepted=training(taken=0),writes=[])
    events=ref.advance(reset=0,accepted=None,writes=[dict(bank=0,set_index=5,way=0,reset_counter=1)])
    assert ref.cells[index(0,5,0)]==2 and events[0]['transition']=='reset'


@pytest.mark.parametrize('position,wanted',[(2,2),(3,3),(4,1)])
def test_taken_position_before_equal_after_filter(position,wanted):
    ref=CounterReference()
    ref.cells[index(0,5,0)]=2
    ref.advance(reset=0,accepted=training(taken=1,position=position),writes=[])
    ref.advance(reset=0,accepted=None,writes=[])
    assert ref.cells[index(0,5,0)]==wanted


@pytest.mark.parametrize('kind,hit',[(2,1),(3,1),(1,0)])
def test_nonconditional_or_miss_does_not_update(kind,hit):
    ref=CounterReference()
    ref.cells[index(0,5,0)]=2
    ref.advance(reset=0,accepted=training(taken=0,branch_type=kind,hit=hit),writes=[])
    assert ref.advance(reset=0,accepted=None,writes=[])==[]
    assert ref.cells[index(0,5,0)]==2


def test_plru_hit_is_two_cycles_after_public_acceptance():
    ref=CounterReference()
    ref.advance(reset=0,accepted=training(taken=1),writes=[])
    assert ref.plru[0][5]==0
    ref.advance(reset=0,accepted=None,writes=[])
    assert ref.plru[0][5]==0
    ref.advance(reset=0,accepted=None,writes=[])
    assert ref.plru[0][5]==5 and victim(ref.plru[0][5])==2


def test_reset_clears_pending_feedback():
    ref=CounterReference()
    ref.advance(reset=0,accepted=training(taken=1),writes=[])
    ref.advance(reset=1,accepted=None,writes=[])
    assert ref.cells==[0]*1024 and ref.pending1 is ref.pending2 is None
