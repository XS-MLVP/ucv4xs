from dataclasses import replace

import pytest

from bpuverify.bpu.case.definitions import PC, POSITION, LATER_POSITION
from bpuverify.bpu.case.tage.learning import qualified_learning_event
from bpuverify.tage.model.semantic import Branch, Context, Feedback, Hint


def stimulus():
    hint = Hint(True, False, True, counter=2, useful=0, alternative=True)
    request = Feedback(PC, Context(), (Branch(POSITION, False, 1, False, True, 2, hint),
        Branch(LATER_POSITION, False, 1, False, True, 2, replace(hint, way=1))))
    return [(2, request)], [(2, (None, POSITION, None, None, None, None, LATER_POSITION, None))]


def test_only_an_accepted_discriminating_two_branch_event_is_reached():
    assert qualified_learning_event(*stimulus())


@pytest.mark.parametrize('fault', ('unaccepted', 'wrong-slot', 'unmatched', 'nonconditional',
    'mispredict', 'weak', 'agreeing-alternate', 'agreeing-base', 'saturated-useful', 'wrong-base', 'other-pc', 'same-owner'))
def test_planning_or_unqualified_learning_cannot_earn_event_credit(fault):
    accepted, slots = stimulus()
    request = accepted[0][1]
    first, second = request.branches
    if fault == 'unaccepted':
        accepted = []
    elif fault == 'wrong-slot':
        slots = [(2, (POSITION, None, None, None, None, None, LATER_POSITION, None))]
    elif fault == 'other-pc':
        request = replace(request, pc=PC + 4)
    elif fault == 'same-owner':
        request = replace(request, branches=(first, replace(second, hint=first.hint)))
    else:
        if fault == 'unmatched': first = replace(first, matched=False)
        elif fault == 'nonconditional': first = replace(first, kind=2)
        elif fault == 'mispredict': first = replace(first, mispredict=True)
        elif fault == 'weak': first = replace(first, hint=replace(first.hint, counter=3))
        elif fault == 'agreeing-alternate': first = replace(first, hint=replace(first.hint, alternate=True))
        elif fault == 'agreeing-base': first = replace(first, hint=replace(first.hint, alternative=False))
        elif fault == 'saturated-useful': first = replace(first, hint=replace(first.hint, useful=3))
        else: first = replace(first, base_counter=1)
        request = replace(request, branches=(first, second))
    if accepted:
        accepted = [(2, request)]
    assert not qualified_learning_event(accepted, slots)
