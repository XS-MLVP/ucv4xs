"""Bounded allowances drop only the declared defect field at a declared address.

Every case is a pure fixture.  No DUT state is seeded, no comparison is muted
globally, and every non-declared difference must survive.
"""
from types import SimpleNamespace

from bpuverify.utage.checker.semantic import UtageSemanticChecker


def prediction(pc, positions=(5, 6, 7, 8), tables=(0, None, None, None), indices=(17, 33)):
    return SimpleNamespace(frame=SimpleNamespace(
        pc=pc,
        positions=positions,
        providers=lambda: tables,
        read=SimpleNamespace(indices=indices),
    ))


def expected_hit_miss():
    return ({"hits": (1, None, None, None), "meta_valid": 1, "0.valid": 1, "0.base": 0,
             "0.hit": 1, "0.taken": 1, "0.predicted": 1, "0.position": 5,
             "0.provider": 0, "0.counter": 4},
            {"hits": (0, None, None, None), "meta_valid": 0, "0.valid": 1, "0.base": 0,
             "0.hit": 0, "0.taken": 1, "0.predicted": 1, "0.position": 5,
             "0.provider": 0, "0.counter": 4})


def test_declared_miss_drops_only_hit_derived_fields_and_is_recorded():
    checker = UtageSemanticChecker()
    checker.allow_known_miss(0x40000800, 5, 'declared tag truncation')
    expected, observed = expected_hit_miss()
    checker._bounded_allowance(prediction(0x40000800), expected, observed)
    assert expected == {"0.valid": 1, "0.base": 0, "0.position": 5}
    assert observed == {"0.valid": 1, "0.base": 0, "0.position": 5}
    assert [event["kind"] for event in checker.allowed_events] == ["known-tag-width-miss"]
    assert checker.allowed_events[0]["pc"] == 0x40000800
    assert checker.allowed_events[0]["position"] == 5


def test_miss_at_an_undeclared_address_or_reverse_difference_is_not_dropped():
    checker = UtageSemanticChecker()
    checker.allow_known_miss(0x40000800, 5, 'declared tag truncation')
    expected, observed = expected_hit_miss()
    checker._bounded_allowance(prediction(0x40000820), expected, observed)
    assert "hits" in expected and "0.hit" in expected
    checker._bounded_allowance(prediction(0x40000800), observed, expected)
    assert "hits" in observed and "0.hit" in observed
    assert checker.allowed_events == []


def test_one_undeclared_hit_difference_keeps_the_whole_comparison():
    checker = UtageSemanticChecker()
    checker.allow_known_miss(0x40000800, 5, 'declared tag truncation')
    expected = {"hits": (1, 1, None, None), "0.hit": 1, "1.hit": 1}
    observed = {"hits": (0, 0, None, None), "0.hit": 0, "1.hit": 0}
    checker._bounded_allowance(prediction(0x40000800, positions=(5, 7, 8, 9)), expected, observed)
    assert expected["hits"] == (1, 1, None, None) and expected["0.hit"] == 1
    assert checker.allowed_events == []


def test_declared_counter_difference_drops_only_the_counter_and_is_recorded():
    checker = UtageSemanticChecker()
    checker.allow_known_counter_difference(0, 17, 'declared ring-slot stale value')
    expected = {"hits": (1, None, None, None), "0.hit": 1, "0.provider": 0, "0.counter": 7}
    observed = {"hits": (1, None, None, None), "0.hit": 1, "0.provider": 0, "0.counter": 5}
    checker._bounded_allowance(prediction(0x40000000), expected, observed)
    assert expected == {"hits": (1, None, None, None), "0.hit": 1, "0.provider": 0}
    assert observed == {"hits": (1, None, None, None), "0.hit": 1, "0.provider": 0}
    assert checker.allowed_events == [dict(kind='known-counter-difference', tick=None, table=0,
        index=17, expected=7, observed=5, reason='declared ring-slot stale value')]


def test_stale_higher_value_at_the_upper_table_is_the_same_declared_defect():
    checker = UtageSemanticChecker()
    checker.allow_known_counter_difference(1, 17, 'declared ring-slot stale value')
    expected = {"0.hit": 1, "0.provider": 1, "0.counter": 0}
    observed = {"0.hit": 1, "0.provider": 1, "0.counter": 2}
    checker._bounded_allowance(prediction(0x40000000, tables=(1, None, None, None), indices=(17, 17)), expected, observed)
    assert expected == {"0.hit": 1, "0.provider": 1}
    assert checker.allowed_events[0]["kind"] == 'known-counter-difference'


def test_wrong_cell_disagreeing_hit_or_other_field_still_fails():
    checker = UtageSemanticChecker()
    checker.allow_known_counter_difference(0, 17, 'declared ring-slot stale value')
    expected = {"0.hit": 1, "0.provider": 0, "0.counter": 5}
    observed = {"0.hit": 1, "0.provider": 0, "0.counter": 6}
    checker._bounded_allowance(prediction(0x40000000, indices=(18, 33)), expected, observed)
    assert expected["0.counter"] == 5
    expected = {"hits": (1, None, None, None), "0.hit": 1, "0.provider": 0, "0.counter": 5}
    observed = {"hits": (0, None, None, None), "0.hit": 0, "0.provider": 0, "0.counter": 4}
    checker._bounded_allowance(prediction(0x40000000), expected, observed)
    assert expected["hits"] == (1, None, None, None) and expected["0.counter"] == 5
    expected = {"0.hit": 1, "0.provider": 0, "0.counter": 5, "0.taken": 1}
    observed = {"0.hit": 1, "0.provider": 0, "0.counter": 4, "0.taken": 0}
    checker._bounded_allowance(prediction(0x40000000), expected, observed)
    # The counter difference is the declared defect and may be dropped, but the
    # direction difference is not declared and must survive for the board.
    assert "0.counter" not in expected and expected["0.taken"] == 1
    assert checker.allowed_events[-1]["kind"] == "known-counter-difference"


def test_declaration_requires_a_concrete_address_or_cell():
    checker = UtageSemanticChecker()
    for call in (lambda: checker.allow_known_miss(0x40000800, 5, ''),
                 lambda: checker.allow_known_counter_difference(0, 512, 'reason'),
                 lambda: checker.allow_known_counter_difference(2, 0, 'reason')):
        try:
            call()
        except ValueError:
            continue
        raise AssertionError('invalid declaration was accepted')
