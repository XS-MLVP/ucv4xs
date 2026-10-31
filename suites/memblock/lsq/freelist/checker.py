def compare(actual, expected, *, phase: str, tick: int):
    if actual.slots[:expected.offered] != expected.slots[:expected.offered]:
        raise AssertionError(f"{phase} tick={tick}: valid slot prefix {actual.slots} != {expected}")
    if actual.can_allocate is not None:
        ready = tuple(i < expected.offered for i in range(3))
        assert actual.can_allocate == ready, (phase, tick, "can_allocate", actual, expected)
    if actual.occupied is not None:
        assert actual.occupied == expected.occupied, (phase, tick, "occupied", actual, expected)
    if actual.empty is not None:
        assert actual.empty == expected.empty, (phase, tick, "empty", actual, expected)
