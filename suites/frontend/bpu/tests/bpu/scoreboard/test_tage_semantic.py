from suites.frontend.bpu.models.configuration import TAGE_TABLES, RESULT_SLOTS
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.bpu.bundle.tage_semantic import HISTORY_PORTS
from suites.frontend.bpu.bpu.checker.tage.semantic import TageSemanticComponentChecker
from suites.frontend.bpu.bpu.monitor.tage.semantic import consumed_context
from suites.frontend.bpu.tage.model.semantic import Context, Events, FOLD_IDS, coordinate
from tests.tage.scoreboard.test_semantic_model import BASES, PC, POSITION, actual_prediction, feedback, learn, lookup


@pytest.mark.parametrize('history', (0, 1, 0x12345678, (1 << 31) - 1))
def test_emitted_component_ports_cover_every_consumed_fold_without_mocking_unused_signals(history):
    assert set(HISTORY_PORTS) == {index for table in FOLD_IDS for index in table}
    full = Context.from_recent(history)
    rows = tuple(SimpleNamespace(foldedHist=SimpleNamespace(as_int=lambda value=full.folds[index]: value))
                 for index in HISTORY_PORTS)
    reduced = consumed_context(rows)
    for table in range(TAGE_TABLES):
        assert coordinate(PC, reduced, table) == coordinate(PC, full, table)


def checker_and_source():
    checker = TageSemanticComponentChecker()
    checker.initialized = True
    lookup(checker.model)
    learn(checker.model, feedback(checker.model))
    for _ in range(2):
        lookup(checker.model)
        learn(checker.model, feedback(checker.model, mispredict=False))
    lookup(checker.model)
    checker.events, checker.input_tick = Events(), 3
    # Live position is not consumed by TAGE; use the model-owned S1 positions.
    bases = (replace(BASES[0], position=0), *BASES[1:])
    from suites.frontend.bpu.tage.model.semantic import decide
    wanted = decide(checker.model.frame, bases, checker.model.selectors)
    actual = actual_prediction(wanted)
    extras = {name: tuple(wanted.get(f'{slot}.{field}', 0) for slot in range(RESULT_SLOTS))
              for name, field in (('fast_valids','fast_valid'),('fast_takens','fast_taken'),('sc_counters','sc_counter'))}
    checker.capture_output(SimpleNamespace(tick=4), actual, bases=bases, enabled=True, extras=extras)
    source = SimpleNamespace(meta_tick=8, prediction=SimpleNamespace(start_pc=PC),
                             meta=SimpleNamespace(resolve={'tage_entries': deepcopy(actual.metas)}))
    return checker, source


def test_public_metadata_uses_the_exact_owned_preceding_frame():
    checker, source = checker_and_source()
    expected = checker.source_expected(source, POSITION)
    assert expected['providerTakenCtr_value'] == 6 and expected['providerUsefulCtr_value'] == 2


def test_disabled_frozen_metadata_is_not_claimed_as_a_fresh_source():
    checker, source = checker_and_source()
    tick, frame, wanted, _, bases = checker.expected.pop()
    checker.expected.append((tick, frame, wanted, False, bases))
    with pytest.raises(ValueError, match='disabled'):
        checker.source_expected(source, POSITION)


@pytest.mark.parametrize('fault', ('pc', 'tick', 'position', 'counter', 'useful', 'way'))
def test_bad_public_metadata_or_association_is_not_repaired_from_observation(fault):
    checker, source = checker_and_source()
    position = POSITION
    if fault == 'pc':
        source.prediction.start_pc += 8
    elif fault == 'tick':
        source.meta_tick += 2
    elif fault == 'position':
        position += 1
    else:
        name = dict(counter='providerTakenCtr_value', useful='providerUsefulCtr_value', way='providerWayIdx')[fault]
        source.meta.resolve['tage_entries'][0][name] ^= 1
    before = deepcopy(checker.model.state())
    with pytest.raises(ScoreboardMismatch) as first:
        checker.source_expected(source, position)
    assert checker.model.state() == before
    with pytest.raises(ScoreboardMismatch) as second:
        checker.source_expected(source, position)
    assert second.value is first.value
