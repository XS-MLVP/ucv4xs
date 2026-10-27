def compare(actual, expected, *, phase, tick):
    assert actual.ready == expected.ready, (phase, tick, "query.ready", actual, expected)
    assert actual.full == expected.full, (phase, tick, "lqFull", actual, expected)
    assert actual.perf_fire == expected.perf_fire, (phase, tick, "perf.fire", actual, expected)
    assert actual.perf_nuke == expected.perf_nuke, (phase, tick, "perf.nuke", actual, expected)
    for lane, (got, want) in enumerate(zip(actual.responses, expected.responses, strict=True)):
        assert got.valid == want.valid, (phase, tick, lane, "response.valid", got, want)
        if want.valid:
            assert got.nuke == want.nuke, (phase, tick, lane, "response.nuke", got, want)
