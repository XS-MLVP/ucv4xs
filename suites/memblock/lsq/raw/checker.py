from dataclasses import asdict


def compare(actual, expected, *, phase, tick):
    for key in ("ready", "full", "perf_fire", "perf_rollback"):
        assert getattr(actual, key) == getattr(expected, key), (phase, tick, key, actual, expected)
    for lane, (got, want) in enumerate(zip(actual.rollbacks, expected.rollbacks, strict=True)):
        assert got.valid == want.valid, (phase, tick, lane, "rollback.valid", got, want)
        if want.valid:
            assert got == want, (phase, tick, lane, "rollback.payload", asdict(got), asdict(want))
    assert actual.training.valid == expected.training.valid, (phase, tick, "training.valid", actual.training, expected.training)
    if expected.training.valid:
        assert actual.training == expected.training, (phase, tick, "training.payload", actual.training, expected.training)
