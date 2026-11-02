"""Clock work scales with live obligations; old evidence must remain intact."""
import pytest
from suites.frontend.bpu.mbtb.checker.lookup_inputs import LookupInputs
from suites.frontend.bpu.mbtb.transaction.types import MbtbLookup
from suites.frontend.bpu.mbtb.model.semantic import Events


class NoHistoryScan(dict):
    reads=0
    max_reads=None

    def items(self):raise AssertionError('clock callback traversed completed lookup history')
    def values(self):raise AssertionError('clock callback traversed completed lookup history')
    def __iter__(self):raise AssertionError('clock callback traversed completed lookup history')

    def __getitem__(self,key):
        self.reads+=1
        if self.max_reads is not None and self.reads>self.max_reads:
            raise AssertionError('source query searched history instead of its tick index')
        return super().__getitem__(key)


def completed_history():
    inputs=LookupInputs()
    for uid in range(1,33):
        tick=uid*6
        inputs.plan(uid,MbtbLookup(0x80000000));inputs.launched(uid,tick)
        inputs.observe(tick,Events(select=True,pc=0x80000000))
        inputs.stage(uid,'advance');inputs.stage_launched(uid,'advance',tick+2)
        inputs.observe(tick+2,Events(advance=True));inputs.observe_output(tick+4)
        inputs.delivered(uid,tick+4)
        inputs.stage(uid,'consume');inputs.stage_launched(uid,'consume',tick+4)
        inputs.observe(tick+4,Events(consume=True))
    inputs.finish()
    inputs._rows=NoHistoryScan(inputs._rows)
    return inputs


@pytest.mark.parametrize('operation',('idle-output','reset','source'))
def test_clock_callbacks_do_not_scan_retained_completed_lookup_history(operation):
    inputs=completed_history()
    if operation=='idle-output':inputs.observe_output(1000)
    elif operation=='reset':inputs.observe(1000,Events(reset=True))
    else:
        inputs._rows.max_reads=1
        origin=inputs.source_at(10)
        assert origin.uid==1 and origin.response_tick==10
    assert len(inputs._rows)==len(inputs._declared)==32


def test_missing_output_boundary_is_not_hidden_by_an_index_pop_or_old_identical_result():
    inputs=LookupInputs();inputs.plan(1,MbtbLookup(0x80000000));inputs.launched(1,2)
    inputs.observe(2,Events(select=True,pc=0x80000000))
    inputs.stage(1,'advance');inputs.observe(4,Events(advance=True))
    with pytest.raises(AssertionError):inputs.observe_output(8)
    with pytest.raises(AssertionError):inputs.finish()


def test_reset_cancels_only_current_work_without_rewriting_old_result_or_source_identity():
    inputs=completed_history();old=inputs.source_at(10)
    inputs.plan(33,MbtbLookup(0x80000000));inputs.launched(33,1000)
    inputs.observe(1000,Events(select=True,pc=0x80000000))
    inputs.observe(1002,Events(reset=True));inputs.observe_output(1004)
    assert inputs._rows[33].state=='reset-cancelled'
    assert inputs._rows[33].response_tick is None
    assert inputs.source_at(10)==old and inputs.source_at(1004) is None
    assert len(inputs._rows)==33
