"""Complete current samples, compact old witnesses and bounded full context."""
from copy import deepcopy

import pytest
from suites.frontend.bpu.bpu.monitor.abtb.history import ObservationHistory, abtb_witness
from suites.frontend.bpu.bpu.checker.abtb.stream import PairChecks
from suites.frontend.bpu.runtime.trace import trace_exports


def frame(tick):
    return dict(tick=tick, state={'cells': tuple(range(52))}, abtb=dict(
        cells=tuple(range(1024)), final=dict(pc=tick), replacers=tuple(
            dict(states=tuple(range(64)), shadow=tuple(range(64)), victim=0) for _ in range(4))))


def test_history_does_not_modify_snapshots_and_bounds_complete_state_retention():
    history = ObservationHistory(abtb_witness, window=4)
    samples = [frame(tick) for tick in range(1, 101)]
    original = deepcopy(samples)
    for sample in samples:
        history.append(sample)
    assert samples == original
    assert len(history) == 100 and len(history.recent) == 4
    assert history[-1] is samples[-1]
    assert history[99] is samples[-1]
    assert [row['tick'] for row in history[-3:]] == [98, 99, 100]
    assert 'cells' not in history[0]['abtb'] and 'state' not in history[0]
    assert 'states' not in history.by_tick[99]['abtb']['replacers'][0]
    assert history.by_tick[1]['abtb']['final'] == samples[0]['abtb']['final']
    assert history.recent[0] is samples[96]
    with pytest.raises(IndexError):
        history[100]
    with pytest.raises(IndexError):
        history[-101]


def test_full_diagnostics_are_opt_in_and_do_not_change_checker_selection():
    assert isinstance(PairChecks({}, coverage=object()).records, ObservationHistory)
    assert isinstance(PairChecks({}).records, list)
    with trace_exports():
        checker = PairChecks({}, coverage=object())
        assert isinstance(checker.records, list)
        assert not checker.compact_history
