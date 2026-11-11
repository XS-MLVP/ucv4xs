def compare(actual, expected, *, phase, tick):
    assert actual.head == expected.head, (phase, tick, "ldWbPtr", actual, expected)
    assert actual.empty == expected.empty, (phase, tick, "lqEmpty", actual, expected)
    assert actual.dequeue_valid == expected.dequeue_valid, (phase, tick, "lqDeq.valid", actual, expected)
    if expected.dequeue_valid:
        assert actual.dequeue_count == expected.dequeue_count, (phase, tick, "lqDeq.count", actual, expected)
    assert actual.recovery_valid == expected.recovery_valid, (phase, tick, "lqRedirect.valid", actual, expected)
    if expected.recovery_valid:
        assert actual.recovery_ptr == expected.recovery_ptr, (phase, tick, "lqRedirect.pointer", actual, expected)
    assert actual.recovery_stall == expected.recovery_stall, (phase, tick, "lqRecoverStall", actual, expected)
