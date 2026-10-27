"""Algorithm expectations, independent history arithmetic and visibility faults."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from bpuverify.sc.model.semantic import Context, DeferredWeights, Events, ScReference, decide
from bpuverify.sc.transaction.types import ScBaseBranch, ScBatchTraining, ScBranchFeedback, ScHistory
from bpuverify.sc.checker.semantic import ScSemanticChecker
from bpuverify.sc.coverage.semantic import ScHistoryCoverage


PC = 0x40000040
BASES = tuple(ScBaseBranch(position, 4) for position in (4, 5, 6, 7))


def lookup(model, *, pc=PC, context=Context(), branches=BASES):
    model.advance(Events(pc=pc, context=context))
    model.advance(Events(advance=True))
    model.advance(Events(select=True, branches=branches))
    return model.prediction


def feedback(prediction, *, outcome=0, slot=0, history=ScHistory()):
    return ScBatchTraining(prediction.read.pc, prediction.metadata(),
        (ScBranchFeedback(prediction.branches[slot].position, outcome, slot),), history)


def settle(model):
    for _ in range(3):
        model.advance()


def test_algorithm_module_has_no_native_or_signal_dependencies():
    module = ast.parse(Path('bpuverify/sc/model/semantic.py').read_text())
    modules = [node.module or '' for node in ast.walk(module) if isinstance(node, ast.ImportFrom)]
    assert modules == ['dataclasses', 'bpuverify.sc.model.threshold', 'bpuverify.sc.transaction.types']
    assert not any(isinstance(node, ast.Import) for node in ast.walk(module))


@pytest.mark.parametrize('history', (0, 1, 127, 128, 255))
def test_history_hash_from_semantic_history_not_debug_indices(history):
    model = ScReference()
    context = Context.from_history(ScHistory(history, history, history & 15, history))
    prediction = lookup(model, context=context)
    folded = (history & 127) ^ (history >> 7)
    assert prediction.read.indices == (8 ^ folded, 8 ^ folded, 8 ^ (history & 15), 8 ^ folded, 8)
    assert prediction.sums == (5,) * 4
    assert prediction.used == (0,) * 4


@pytest.mark.parametrize('counter', range(8))
def test_base_confidence_selects_bias_feature_and_strict_threshold(counter):
    model = ScReference()
    branches = tuple(replace(branch, tage_counter=counter) for branch in BASES)
    read = model.snapshot(PC, Context())
    shift = {0: 4, 7: 4, 3: 6, 4: 6}.get(counter, 5)
    # At exact |sum|=5 the strict confidence test must not correct.
    at = decide(read, branches, (5 << shift,) * 4)
    below = decide(read, branches, (4 << shift,) * 4)
    assert at.used == (0,) * 4
    assert below.used == (1,) * 4
    assert at.metadata()['scBiasLowerBits'] == ((2 if counter in (3, 4) else 0) + (counter >= 4),) * 4


@pytest.mark.parametrize('direction', (0, 1))
def test_learning_owns_weights_and_waits_for_physical_visibility(direction):
    model = ScReference()
    cold = lookup(model)
    model.advance(Events(feedback=feedback(cold, outcome=direction)))
    assert model.thresholds.values == (1130,) * 4
    model.advance()
    assert model.thresholds.values == (1130, 1131 if direction == 0 else 1129, 1130, 1130)
    assert model.snapshot(PC, Context()).weights == cold.read.weights
    model.advance()
    assert model.commits == 0
    model.advance()
    hot = lookup(model)
    assert model.commits == 5
    assert hot.sums[0] == (-5 if direction == 0 else 15)
    assert hot.sums[1:] == (5,) * 3
    assert cold.sums == (5,) * 4  # Previously issued snapshots are immutable.


def test_outstanding_read_snapshot_is_not_replaced_by_later_weight_commit():
    model = ScReference()
    cold = lookup(model)
    model.advance(Events(feedback=feedback(cold)))
    model.advance()
    model.advance(Events(pc=PC))
    model.advance(Events(advance=True))  # Pending writes retire here.
    model.advance(Events(select=True, branches=BASES))
    assert model.commits == 5
    assert model.prediction.sums == (5,) * 4
    assert lookup(model).sums[0] == -5


def test_same_way_votes_are_net_before_one_saturation_step():
    model = ScReference()
    bases = tuple(ScBaseBranch(position, 4) for position in (0, 5, 10, 15))
    prediction = lookup(model, branches=bases)
    transaction = ScBatchTraining(PC, prediction.metadata(), tuple(
        ScBranchFeedback(branch.position, taken, slot)
        for slot, (branch, taken) in enumerate(zip(bases, (1, 1, 1, 0), strict=True))))
    model.advance(Events(feedback=transaction))
    settle(model)
    assert model.thresholds.values == (1128, 1130, 1130, 1130)
    assert lookup(model, branches=bases).sums == (25,) * 4


def test_invalid_common_history_disables_only_global_and_backward_learning():
    model = ScReference()
    context = Context(common_valid=False)
    cold = lookup(model, context=context)
    model.advance(Events(feedback=feedback(cold), feedback_context=context))
    settle(model)
    assert model.commits == 3
    assert lookup(model, context=context).sums[0] == -1
    assert model.memory[1] == model.memory[2] == {}


@pytest.mark.parametrize('kind', ('disabled', 'miss', 'nonconditional', 'provider-invalid', 'correct-agreement'))
def test_feedback_qualification_does_not_create_fake_learning(kind):
    model = ScReference()
    prediction = lookup(model)
    transaction = feedback(prediction)
    branch, = transaction.branches
    if kind == 'miss':
        transaction = replace(transaction, branches=(replace(branch, mbtb_hit=0),))
    elif kind == 'nonconditional':
        transaction = replace(transaction, branches=(replace(branch, branch_type=2),))
    elif kind == 'provider-invalid':
        transaction.meta['tagePredValid'] = (0,) * 4
    elif kind == 'correct-agreement':
        transaction.meta['useScPred'] = (1,) * 4
        transaction = replace(transaction, branches=(replace(branch, actual_taken=1),))
    model.advance(Events(feedback=transaction, enabled=kind != 'disabled'))
    settle(model)
    assert model.commits == 0
    assert model.thresholds.values == (1130,) * 4


def test_reset_discards_learning_writes_and_lookup_context():
    model = ScReference()
    cold = lookup(model)
    model.advance(Events(feedback=feedback(cold)))
    model.advance()
    model.advance(Events(reset=True))
    settle(model)
    assert model.commits == 0
    assert model.prediction is None
    assert model.thresholds.values == (1130,) * 4
    assert lookup(model).sums == (5,) * 4


def test_read_bank_conflict_is_rejected_without_hardware_observation():
    model = ScReference()
    prediction = lookup(model)
    with pytest.raises(AssertionError, match='conflicting'):
        model.advance(Events(pc=PC, feedback=feedback(prediction)))


def test_masked_pending_writes_merge_without_touching_neighbours():
    cache = DeferredWeights()
    cache.advance(True, (3, (-1, None, None, None)))
    cache.advance(True, (3, (None, 2, None, None)))
    assert cache.advance(False).patch == (-1, 2, None, None)
    cache.advance(True, (3, (None, 2, None, None)))
    assert cache.advance(False) is None
    cache.advance(True, (3, (None, 3, None, None)))
    assert cache.advance(False).patch == (-1, 3, None, None)


@pytest.mark.parametrize('field,width', (('path',31), ('global_history',8), ('backward',4), ('loop',8)))
def test_history_width_validation(field, width):
    with pytest.raises(ValueError):
        ScHistory(**{field: 1 << width})


@pytest.mark.parametrize('direction', (0, 1))
def test_signed_weight_saturation_is_bounded_not_wrapped(direction):
    model = ScReference()
    cold = lookup(model)
    for _ in range(40):
        model.advance(Events(feedback=feedback(cold, outcome=direction)))
        settle(model)
    hot = lookup(model)
    assert hot.sums[0] == (-315 if direction == 0 else 315)
    assert hot.used[0] == 1
    assert hot.sums[1:] == (5,) * 3


def actual_metadata(prediction):
    actual = prediction.metadata()
    actual['debug'] = dict(zip(('predPathIdx','predGlobalIdx','predBWIdx','predImliIdx','predBiasIdx'),
                               ((value,) if table < 3 else value
                                for table, value in enumerate(prediction.read.indices)), strict=True))
    for table, key in enumerate(('scPathTakenVec','scGlobalTakenVec','scBWTakenVec','scImliTakenVec','scBiasTakenVec')):
        actual['debug'][key] = tuple(row[table] for row in prediction.components)
    return actual


@pytest.mark.parametrize('field', ('scBiasLowerBits','scPred','useScPred','sumAboveThres',
    'tageCtr','tagePred','tagePredValid','predPathIdx','predGlobalIdx','predBWIdx','predImliIdx',
    'predBiasIdx','scPathTakenVec','scGlobalTakenVec','scBWTakenVec','scImliTakenVec','scBiasTakenVec'))
def test_wrong_public_fields_fail_without_resynchronizing_reference(field):
    checker = ScSemanticChecker()
    checker.initialized = True
    checker.capture_input(SimpleNamespace(tick=1), Events(pc=PC))
    checker.capture_input(SimpleNamespace(tick=3), Events(advance=True))
    checker.capture_input(SimpleNamespace(tick=5), Events(select=True, branches=BASES))
    actual = actual_metadata(checker.model.prediction)
    container = actual if field in actual else actual['debug']
    value = container[field]
    container[field] = (value[0] ^ 1, *value[1:]) if isinstance(value, tuple) else value ^ 1
    state = deepcopy(checker.model.state())
    checker.capture_output(SimpleNamespace(tick=6), actual)
    with pytest.raises(AssertionError):
        checker.raise_failure()
    assert checker.model.state() == state
    assert checker.board.status.failed == 1


def test_checked_coverage_follows_successful_comparison_not_model_progress():
    coverage = ScHistoryCoverage()
    checker = ScSemanticChecker(coverage=coverage)
    checker.initialized = True
    checker.capture_input(SimpleNamespace(tick=1), Events(pc=PC))
    checker.capture_input(SimpleNamespace(tick=3), Events(advance=True))
    checker.capture_input(SimpleNamespace(tick=5), Events(select=True, branches=BASES))
    actual = actual_metadata(checker.model.prediction)
    actual['scPred'] = (0,) * 4
    checker.capture_output(SimpleNamespace(tick=6), actual)
    assert coverage.groups['reached'].coverage > 0
    assert coverage.groups['checked'].coverage == 0


def test_reset_cancels_old_history_coverage_obligations():
    coverage = ScHistoryCoverage()
    model = ScReference()
    prediction = lookup(model)
    coverage.accept(Events(pc=PC), 1)
    coverage.accept(Events(reset=True), 3)
    coverage.consume(prediction, 4)
    assert coverage.groups['reached'].coverage > 0
    assert coverage.groups['checked'].coverage == 0
