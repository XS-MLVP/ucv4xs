def compare(actual, expected, *, phase, tick):
    for field in ("flush", "mmio_select", "slave_valid"):
        assert getattr(actual, field) == getattr(expected, field), (phase, tick, field, actual, expected)
    if expected.slave_valid:
        assert actual.slave_id == expected.slave_id, (phase, tick, "slave_id", actual, expected)
    for field in ("bus", "mmio_wakeup", "nc_wakeup", "mmio", "nc", "exception"):
        got, want = getattr(actual, field), getattr(expected, field)
        assert got.valid == want.valid, (phase, tick, field + ".valid", got, want)
        if want.valid:
            assert got == want, (phase, tick, field + ".payload", got, want)
