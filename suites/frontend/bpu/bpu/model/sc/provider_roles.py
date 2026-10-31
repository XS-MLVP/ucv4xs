"""Small pure rules for real provider role preparation, not DUT state seeding."""
PROFILES = {
    'negative_mid_weak': (2, 3),
    'negative_weak_mid': (3, 2),
    'positive_weak_mid': (4, 5),
    'positive_mid_weak': (5, 4),
}


def selectors(counters):
    return tuple(2 * int(value in (3, 4)) + int(value >= 4) for value in counters)


def next_feedback(counters, goals):
    assert len(counters) == len(goals) == 2
    assert all(type(value) is int and 0 <= value <= 7 for value in (*counters, *goals))
    for lane, (value, goal) in enumerate(zip(counters, goals, strict=True)):
        if value != goal:
            return lane, int(value < goal)
    return None


def validate_transition(before, after, *, lane, taken, mispredict):
    assert lane in (0, 1) and taken in (0, 1) and mispredict in (0, 1)
    assert len(before) == len(after) == 2
    assert after[1 - lane] == before[1 - lane], dict(field='unchosen_provider',
        expected=before[1 - lane], actual=after[1 - lane])
    prior, actual = before[lane], after[lane]
    assert len(prior) == len(actual) == 3
    assert all(type(value) is int and 0 <= value <= 7 for value in (prior[2], actual[2]))
    if prior[:2] == actual[:2]:
        expected = max(0, min(7, prior[2] + (1 if taken else -1)))
        assert actual[2] == expected, dict(field='provider_counter', expected=expected, actual=actual[2])
        return 'update_same_provider'
    assert mispredict == 1, dict(field='allocation_requires_real_mispredict')
    assert actual[0] > prior[0], dict(field='allocation_must_use_longer_history_table', before=prior, after=actual)
    assert actual[2] == (4 if taken else 3), dict(field='allocated_weak_counter', taken=taken, actual=actual[2])
    return 'allocate_weak_positive' if taken else 'allocate_weak_negative'

