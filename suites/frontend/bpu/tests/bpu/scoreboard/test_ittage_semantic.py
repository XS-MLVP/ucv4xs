"""Component input events and historical table snapshots, never DUT seeds."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from toffee import ScoreboardMismatch

from bpuverify.bpu.checker.ittage_semantic import IttageSemanticComponentChecker, read_context
from bpuverify.bpu.monitor.ittage_semantic import component_events
from bpuverify.ittage.model.semantic import Context, Entry, Events, Metadata, Outcome, Target, coordinates
from tests.ittage.scoreboard.test_semantic_reference import actual_value


PC, A, B = 0x8000100C, 0x80004000, 0x80008000


def scalar(value):
    return SimpleNamespace(as_int=lambda: value)


def inputs(*, training=False, qualified=True):
    context = tuple(SimpleNamespace(index=scalar(0), tag=scalar(0), secondary=scalar(0)) for _ in range(5))
    metadata = SimpleNamespace(provider=SimpleNamespace(valid=scalar(0), bits=scalar(3)),
        altProvider=SimpleNamespace(valid=scalar(0), bits=scalar(3)),
        allocate=SimpleNamespace(valid=scalar(1), bits=scalar(0)), altDiffers=scalar(0))
    branch = SimpleNamespace(valid=scalar(1), taken=scalar(1), branch_type=scalar(3),
        ras_action=scalar(0 if qualified else 1), target=scalar(A // 2), mispredict=scalar(1))
    return SimpleNamespace(reset=scalar(0), enabled=scalar(1), ready=scalar(1),
        pc=scalar(PC // 2), accept=scalar(1), access=scalar(1), select=scalar(1), context=context,
        train_valid=scalar(int(training)), train_pc=scalar(PC // 2), train_context=context,
        train_meta=metadata, branches=(branch,))


def test_component_inputs_decode_real_byte_events_without_a_launch_delay():
    event = component_events(inputs(training=True))
    assert event == Events(pc=PC, context=Context(), access=True, select=True,
        feedback=Outcome(PC, Context(), Metadata(allocation=0), A, mispredict=True))
    assert component_events(inputs(training=True, qualified=False)).feedback is None


def checker():
    reference = IttageSemanticComponentChecker()
    reference.capture_input(SimpleNamespace(tick=0), Events(reset=True))
    reference.capture_output(SimpleNamespace(tick=1), SimpleNamespace(), visible=False, baseline=0)
    bank, index, tag = coordinates(PC, Context(), 0)
    reference.model.memories[0][bank][index] = Entry(True, tag, 2, 1, Target(A % (1 << 20)))
    reference.capture_input(SimpleNamespace(tick=2), Events(pc=PC))
    reference.capture_output(SimpleNamespace(tick=3), SimpleNamespace(meta={'valid':0},hit=0),visible=False,baseline=0)
    reference.capture_input(SimpleNamespace(tick=4), Events(access=True))
    reference.capture_output(SimpleNamespace(tick=5), SimpleNamespace(meta={'valid':0},hit=0),visible=False,baseline=0)
    return reference


def test_public_source_uses_selected_read_snapshot_not_current_memory():
    reference = checker()
    snapshot = read_context(reference.model, reference.model.read)
    assert snapshot.entries[0].target == A // 2
    bank, index, tag = coordinates(PC, Context(), 0)
    reference.model.memories[0][bank][index] = Entry(True,tag,0,0,Target(B % (1 << 20)))
    reference.capture_input(SimpleNamespace(tick=6), Events(select=True))
    reference.capture_output(SimpleNamespace(tick=7),actual_value(reference.model.prediction),visible=True,baseline=B//2)
    source=SimpleNamespace(meta_tick=7,prediction=SimpleNamespace(start_pc=PC//2))
    expected,baseline=reference.source_context(source)
    assert (expected.entries[0].target,expected.entries[0].counter,expected.entries[0].useful)==(A//2,2,1)
    assert baseline==B//2
    expected.entries.clear()
    assert reference.source_context(source)[0].entries[0].target==A//2


@pytest.mark.parametrize('fault', ['target', 'counter', 'pc', 'wrong-tick'])
def test_wrong_result_or_source_association_is_not_repaired_from_observation(fault):
    reference = checker()
    reference.capture_input(SimpleNamespace(tick=6), Events(select=True))
    actual=actual_value(reference.model.prediction)
    if fault=='target':actual=replace(actual,target=B)
    elif fault=='counter':actual=replace(actual,meta={**actual.meta,'providerCnt_value':0})
    reference.capture_output(SimpleNamespace(tick=7),actual,visible=True,baseline=A//2)
    source=SimpleNamespace(meta_tick=7 if fault!='wrong-tick' else 9,
        prediction=SimpleNamespace(start_pc=PC//2+int(fault=='pc')))
    with pytest.raises(ScoreboardMismatch):reference.source_context(source)
    assert reference.model.prediction.confidence==2 and reference.model.prediction.target==A


@pytest.mark.parametrize('fault', ['counter', 'cursor'])
def test_checked_hardware_timing_cannot_shift_the_independent_model(fault):
    reference=IttageSemanticComponentChecker(audit=SimpleNamespace(
        counter=0,tables=[(0,0)]*5,raise_failure=lambda:None))
    reference.capture_input(SimpleNamespace(tick=0),Events(reset=True))
    reference.capture_output(SimpleNamespace(tick=1),SimpleNamespace(),visible=False,baseline=0)
    reference.capture_input(SimpleNamespace(tick=2),Events())
    if fault=='counter':reference.audit.counter=1
    else:reference.audit.tables[0]=(0,1)
    reference.capture_output(SimpleNamespace(tick=3),SimpleNamespace(meta={'valid':0},hit=0),
        visible=False,baseline=0)
    with pytest.raises(ScoreboardMismatch):reference.raise_failure()
    assert reference.model.tick==0 and reference.model.maintenance==[(False,0)]*5
