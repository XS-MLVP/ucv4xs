"""Public response properties, independent of physical replacement choices."""


def branch_facts(prediction):
    facts = []
    for slot, entry in enumerate(prediction.entries):
        if entry.valid:
            counter = prediction.meta_entries[slot // 5][slot % 5]['counter_value']
            facts.append((entry.position, entry.branch_type, entry.ras_action,
                          entry.target, int(entry.taken), counter))
    return tuple(sorted(facts))


def check_payload(case, actual, neighbor):
    assert branch_facts(actual) == tuple(sorted((*case.wanted, neighbor))), 'payload/type/target/direction or unrelated resident changed'


def check_destination(case, actual):
    matches = [(slot, entry) for slot, entry in enumerate(actual.entries)
               if entry.valid and entry.position == 2]
    assert len(matches) == 1, 'corrected identity must be unique'
    slot, entry = matches[0]
    assert (entry.branch_type, entry.ras_action, entry.target) == (3, 0, case.target)
    assert ('victim' if slot % 5 == 4 else 'main') == case.destination, 'stale exposure is not current residency'
