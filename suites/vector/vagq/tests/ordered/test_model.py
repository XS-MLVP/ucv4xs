"""Independent ordered-permit model qualification."""
import pytest

from vagqverify.ordered.model import State
from vagqverify.ordered.types import Beat, Entry, Permit, Redirect, SplitDone

pytestmark = pytest.mark.toffee_functional_coverage(False)
ORDERED_LOAD = 0b110
ORDERED_STORE = 0b111
UNORDERED_LOAD = 0b100


def entries(changes=None):
    result = [Entry() for _ in range(8)]
    for index, entry in (changes or {}).items():
        result[index] = entry
    return tuple(result)


def ordered(index, *, uop=1, rob=10, flag=0, last=False, exception=False, state=3):
    return Entry(True, ORDERED_LOAD, flag, rob, uop, last, exception, state)


def beat(entry_map=None, *, split=None, redirect=None):
    return Beat(
        entries=entries(entry_map),
        split_done=split or SplitDone(),
        redirect=redirect or Redirect(),
    )


def test_invalid_unordered_store_and_first_uop_are_directly_allowed():
    state = State()
    current = entries({
            0: Entry(),
            1: Entry(True, UNORDERED_LOAD, uop_idx=3),
            2: Entry(True, ORDERED_STORE, uop_idx=3),
            3: ordered(3, uop=0),
            4: ordered(4, uop=2),
        })
    assert state.observe(current).ordered_can_proceed == (True, True, True, True, False, True, True, True)


def test_permit_requires_exact_rob_and_uop_identity():
    state = State((None, Permit(0, 10, 2), None, None, None, None, None, None))
    current = entries({
        1: ordered(1, uop=2, rob=10),
        2: ordered(2, uop=2, rob=11),
        3: ordered(3, uop=3, rob=10),
    })
    assert state.observe(current).ordered_can_proceed == (True, True, False, False, True, True, True, True)


def test_middle_completion_consumes_old_and_handoffs_to_adjacent():
    state = State((Permit(0, 10, 1), None, None, None, None, None, None, None))
    current = beat(
        {0: ordered(0, uop=1, rob=10), 1: ordered(1, uop=2, rob=10)},
        split=SplitDone(True, 0),
    )
    following = state.following(current)
    assert following.permits[0] is None
    assert following.permits[1] == Permit(0, 10, 2)


def test_last_or_exception_consumes_without_handoff_and_entry_seven_wraps_to_zero():
    last = beat({2: ordered(2, uop=2, last=True)}, split=SplitDone(True, 2))
    state = State((None, None, Permit(0, 10, 2), None, None, None, None, None))
    assert state.following(last).permits[2] is None

    exceptional = beat({2: ordered(2, uop=2, exception=True)}, split=SplitDone(True, 2))
    assert state.following(exceptional).permits[2] is None

    wrap = beat({7: ordered(7, uop=0, rob=20)}, split=SplitDone(True, 7))
    wrapped = State().following(wrap)
    assert wrapped.permits[0] == Permit(0, 20, 1)


def test_redirect_flushes_self_and_younger_but_preserves_older():
    state = State((Permit(0, 9, 1), Permit(0, 10, 1), Permit(0, 11, 1), None, None, None, None, None))
    self_flush = beat(redirect=Redirect(True, 1, 0, 10))
    result = state.following(self_flush)
    assert result.permits[:3] == (Permit(0, 9, 1), None, None)

    younger_flush = beat(redirect=Redirect(True, 0, 0, 10))
    result = state.following(younger_flush)
    assert result.permits[:3] == (Permit(0, 9, 1), Permit(0, 10, 1), None)


def test_redirect_flag_wrap_flushes_the_other_circular_half():
    state = State((Permit(0, 5, 1), Permit(1, 2, 1), None, None, None, None, None, None))
    result = state.following(beat(redirect=Redirect(True, 0, 1, 1)))
    assert result.permits[0] is None
    assert result.permits[1] is None


@pytest.mark.parametrize('factory', [
    lambda: Entry(uop_type=8), lambda: Entry(rob_value=512),
    lambda: SplitDone(True, 8), lambda: Redirect(True, 2),
    lambda: Permit(0, 0, 8),
])
def test_domain_rejects_truncating_invalid_values(factory):
    with pytest.raises(ValueError):
        factory()
