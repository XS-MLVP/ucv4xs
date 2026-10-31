import pytest
from suites.frontend.bpu.abtb.model.state.counter import CounterReference
from suites.frontend.bpu.abtb.model.state.counter import index
from suites.frontend.bpu.abtb.model.state.counter import touch
from tests.abtb.scoreboard.test_counter_model import training


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('way', range(4))
@pytest.mark.parametrize('old', range(4))
@pytest.mark.parametrize('taken', (0, 1))
def test_hand_calculated_reset_wins_all_cells_and_values(bank, way, old, taken):
    reference = CounterReference()
    tx = training(bank=bank, taken=taken)
    tx['meta']['entries'][way] = tx['meta']['entries'][0]
    if way != 0:
        tx['meta']['entries'][0] = dict(hit=0, position=9, attribute=dict(branchType=1, rasAction=0))
    cell = index(bank, 5, way)
    neighbor = index((bank + 1) % 4, 6, way)
    reference.cells[cell], reference.cells[neighbor] = old, 3
    reference.advance(reset=0, accepted=tx, writes=[])
    updates = reference.advance(reset=0, accepted=None,
        writes=[dict(bank=bank, set_index=5, way=way, reset_counter=1)])
    assert reference.cells[cell] == 2 and reference.cells[neighbor] == 3
    assert updates == [dict(bank=bank, set_index=5, way=way, before=old,
                           after=2, transition='reset', feedback=None)]
    assert reference.plru[bank][5] == touch(0, way)
