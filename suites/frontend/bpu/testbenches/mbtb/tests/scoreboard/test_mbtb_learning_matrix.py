"""Hand properties versus representative wrong rules, independent of live RTL."""
from dataclasses import replace
from types import SimpleNamespace as NS
import inspect
import textwrap
import pytest

from suites.frontend.bpu.testbenches.bpu.model.main_sources import source_entries
from suites.frontend.bpu.testbenches.mbtb.model.learning_matrix import PAYLOAD_CASES
from suites.frontend.bpu.testbenches.mbtb.model.learning_matrix import RESIDENCY_CASES
from suites.frontend.bpu.testbenches.mbtb.model.semantic import MbtbReference
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Events
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Feedback
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Branch
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Source
from suites.frontend.bpu.testbenches.mbtb.model.semantic import conditional_direction_update
import suites.frontend.bpu.testbenches.mbtb.model.semantic as semantic
from suites.frontend.bpu.testbenches.mbtb.checker.learning_matrix import check_payload
from suites.frontend.bpu.testbenches.mbtb.checker.learning_matrix import check_destination


def lookup(model, pc):
    for _ in range(2):
        model.advance(Events(pc=pc, select=True, advance=True, consume=True))
    return model.frame


def learn(model, frame, pc, position, kind, target, taken=True):
    model.advance(Events(feedback=Feedback((pc, (pc // 16 + 1) * 16), source_entries(frame),
        (Branch(target, taken, position, kind, mispredict=True),))))
    for _ in range(12):
        model.advance()


def execute(case, method=None):
    model = MbtbReference()
    if method is not None:
        model._learning_effects = method.__get__(model, MbtbReference)
    if case.initial_kind is not None:
        learn(model, lookup(model, case.pc), case.pc, case.position, case.initial_kind, case.target)
    learn(model, lookup(model, case.pc), case.pc, case.position, case.resolved_kind, case.successor, False)
    frame = lookup(model, case.pc).values()
    return tuple((frame[f'{s}.position'], frame[f'{s}.kind'], frame[f'{s}.action'],
                  frame[f'{s}.target'], frame[f'{s}.taken'], frame[f'{s}.counter'])
                 for s in range(10) if frame[f'{s}.valid'])


@pytest.mark.parametrize('case', PAYLOAD_CASES, ids=lambda c: c.label)
def test_independent_state_model_respects_the_declared_payload_outcome(case):
    assert execute(case) == case.wanted


def test_reclassification_not_existing_conditional_is_needed_to_kill_the_missing_NT_rule():
    original = MbtbReference._learning_effects
    code = textwrap.dedent(inspect.getsource(original))
    block = '''        if correction is not None and correction.kind == 1 and not correction.taken:
            # Preserve payload, including on a cold miss or reclassification.
            # Direction processing below still consumes conditional feedback.
            correction = None
'''
    assert code.count(block) == 1
    namespace = dict(original.__globals__)
    exec(code.replace(block, ''), namespace)
    wrong = namespace['_learning_effects']
    warm = next(c for c in PAYLOAD_CASES if c.mode == 'conditional-nt')
    corrected = replace(warm, mode='reclassified-nt')
    assert execute(warm, wrong) == warm.wanted  # Original warm sample misses this fault.
    assert execute(corrected, wrong) != corrected.wanted


@pytest.mark.parametrize('fault', ('target', 'type', 'direction', 'neighbor'))
def test_response_property_rejects_bad_values_for_the_same_legal_case(fault):
    case = next(c for c in PAYLOAD_CASES if c.mode == 'reclassified-nt')
    peer = (8, 3, 0, case.pc + 0x700, 1, 2)
    def prediction(facts):
        entries = [NS(valid=1, position=p, branch_type=k, ras_action=a, target=t, taken=b) for p,k,a,t,b,_ in facts]
        return NS(entries=entries, meta_entries=([dict(counter_value=c) for *_,c in facts],))
    check_payload(case, prediction((*case.wanted, peer)), peer)
    wrong = [list(case.wanted[0]), list(peer)]
    if fault == 'target': wrong[0][3] = case.successor
    elif fault == 'type': wrong[0][1] = 1
    elif fault == 'direction': wrong[0][4] ^= 1
    else: wrong[1][3] += 2
    with pytest.raises(AssertionError, match='payload/type/target/direction'):
        check_payload(case, prediction(wrong), peer)


@pytest.mark.parametrize('case', RESIDENCY_CASES, ids=lambda c: c.label)
def test_stale_exposure_cannot_redefine_the_expected_destination(case):
    def prediction(destination):
        slot = 5 * case.alignment + (4 if destination == 'victim' else 3)
        entries = [NS(valid=0) for _ in range(10)]
        entries[slot] = NS(valid=1, position=2, branch_type=3, ras_action=0, target=case.target)
        return NS(entries=entries)
    check_destination(case, prediction(case.destination))
    with pytest.raises(AssertionError, match='stale exposure'):
        check_destination(case, prediction('main' if case.destination == 'victim' else 'victim'))


@pytest.mark.parametrize('hit', (False, True))
@pytest.mark.parametrize('old_kind', (1, 3))
@pytest.mark.parametrize('corrected', (False, True))
def test_actual_type_correction_does_not_drop_original_hit_or_no_correction_qualification(hit, old_kind, corrected):
    source = Source(hit, 5, old_kind, counter=2)
    outcome = Branch(0x40000806, False, 5, 1, mispredict=corrected)
    wanted = 1 if hit and (old_kind == 1 or corrected) else None
    assert conditional_direction_update(source, outcome) == wanted


def test_same_tag_different_position_is_not_direction_evidence():
    source = Source(True, 5, 3, counter=2)
    outcome = Branch(0x40000807, False, 6, 1, mispredict=True)
    # Core supplies only a same-position conditional; direct helper must not
    # accept arbitrary differently-owned branch facts either.
    assert conditional_direction_update(source, outcome) is None
    assert conditional_direction_update(source, replace(outcome, position=5, kind=3)) is None


def test_old_predicted_type_only_rule_is_rejected_by_the_same_new_class(monkeypatch):
    case = next(c for c in PAYLOAD_CASES if c.mode == 'reclassified-nt')
    original = semantic.conditional_direction_update
    monkeypatch.setattr(semantic, 'conditional_direction_update',
        lambda source, result: None if source.kind != 1 else original(source, result))
    assert execute(case) != case.wanted
