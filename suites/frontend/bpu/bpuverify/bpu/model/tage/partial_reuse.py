"""A serviced identity frees capacity; pending logical results still belong."""
from dataclasses import replace
from bpuverify.bpu.model.tage.full_neighbor_migration import (
    PC, NEIGHBOR_NAMES as FIRST_NEIGHBORS, HISTORY_PATHS as BASE_PATHS,
    preparation as first_preparation)
from bpuverify.bpu.model.tage.neighbor_migration import neighbor_preparation, expected_profile as base_profile
from bpuverify.bpu.model.tage.dual_migration import Step, OUTCOMES

NEIGHBOR_NAMES = (*FIRST_NEIGHBORS, 'neighbor-fourth')
HISTORY_PATHS = dict(BASE_PATHS, **{'neighbor-fourth': PC + 0x400})
INPUT_NAMES = (*FIRST_NEIGHBORS, 'current', 'neighbor-fourth', 'old-first', 'old-second')
INITIAL_INPUTS = 4


def preparation():
    yield from first_preparation()
    name = NEIGHBOR_NAMES[-1]
    for label, counter in (('strong', 2), ('weak', 1)):
        yield Step(f'{name}-shared-base-{label}', name, ((0, False, False), (1, False, True)),
                   ((0, counter), (None, None)), False)
    for step in neighbor_preparation():
        yield replace(step, name=f'{name}:{step.name}', context=name)


def expected_profile(name, *, serviced):
    if name not in HISTORY_PATHS:
        raise ValueError('partial reuse needs a declared history')
    return base_profile('neighbor' if name in NEIGHBOR_NAMES else name, serviced=serviced)


def mixed_profile(name):
    return expected_profile(name, serviced=name == NEIGHBOR_NAMES[0])
