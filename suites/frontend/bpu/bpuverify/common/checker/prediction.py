"""BPU-domain expectations shared by predictor Scoreboards."""

from __future__ import annotations

from typing import Any


class _ObserveOnly:
    __slots__ = ()

    def __repr__(self) -> str:
        return "OBSERVE_ONLY"


OBSERVE_ONLY = _ObserveOnly()


def observation_expected(request: Any, context: Any) -> _ObserveOnly:
    """Allow serial scenarios to inspect an actual and assert afterwards."""

    del request, context
    return OBSERVE_ONLY


def compare_prediction(expected: Any, actual: Any) -> None:
    """Compare an exact value or invoke an explicit prediction assertion."""

    if expected is OBSERVE_ONLY:
        return
    if callable(expected):
        expected(actual)
        return
    assert actual == expected

