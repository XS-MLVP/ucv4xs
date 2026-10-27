"""Select stimulus from independent replacement expectations, not DUT misses."""


def expected_victim(agent, residents):
    model = agent.reference.model
    entry = model.entries[model.victim()]
    matches = [vector for vector in residents if model.key(vector.pc) == entry.key]
    if len(matches) != 1 or not entry.confidence:
        raise ValueError('replacement stimulus requires exactly one live modeled resident')
    return matches[0]
