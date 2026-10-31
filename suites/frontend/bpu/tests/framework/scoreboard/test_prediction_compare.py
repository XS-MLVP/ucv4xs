from __future__ import annotations

from dataclasses import dataclass

import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.checkers.prediction import compare_prediction
from suites.frontend.bpu.checkers.prediction import observation_expected
from toffee import Scoreboard


@dataclass(frozen=True)
class Prediction:
    valid: int
    target: int


@pytest.mark.feature("ENV-SCB-002")
def test_prediction_compare_supports_values_and_predicates():
    scoreboard = Scoreboard("prediction", compare=compare_prediction)
    scoreboard.check(
        expected=Prediction(1, 0x1000),
        actual=Prediction(1, 0x1000),
    )
    scoreboard.check(
        expected=lambda actual: (
            None if actual.valid else (_ for _ in ()).throw(
                AssertionError("prediction must be valid")
            )
        ),
        actual=Prediction(1, 0x1000),
    )

    with pytest.raises(ScoreboardMismatch, match="target"):
        scoreboard.check(
            expected=Prediction(1, 0x1000),
            actual=Prediction(1, 0x2000),
        )


@pytest.mark.feature("ENV-SCB-002")
def test_observe_only_expected_routes_without_comparing():
    scoreboard = Scoreboard("observe", compare=compare_prediction)
    expected = observation_expected(object(), object())
    scoreboard.check(
        expected=expected,
        actual=Prediction(0, 0xDEAD),
    )

