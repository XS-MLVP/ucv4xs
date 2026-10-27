"""A full retained hit updates a migrated identity, not a replacement victim."""
from dataclasses import replace
from bpuverify.bpu.model.tage.neighbor_migration import (
    PC, OUTCOMES, HISTORY_PATHS as BASE_PATHS, neighbor_preparation, expected_profile as base_profile)
from bpuverify.bpu.model.tage.dual_migration import Step

NEIGHBOR_NAMES = ('neighbor', 'neighbor-second', 'neighbor-third')
HISTORY_PATHS = dict(BASE_PATHS, **{'neighbor-second': PC + 0x100, 'neighbor-third': PC + 0x200})
INPUT_NAMES = (*NEIGHBOR_NAMES, 'current', 'old-first', 'old-second')


def preparation():
    for index, name in enumerate(NEIGHBOR_NAMES):
        # Later histories start with the shared Main branch pair at1/3, not
        # the0/1 left by the original migration. Normal NT outcomes restore
        # the declared base state before the common eight-step discovery.
        if index:
            for label, counter in (('strong', 2), ('weak', 1)):
                yield Step(f'{name}-shared-base-{label}', name, ((0, False, False), (1, False, True)),
                           ((0, counter), (None, None)), False)
        for step in neighbor_preparation():
            yield replace(step, name=step.name if index == 0 else f'{name}:{step.name}', context=name)


def expected_profile(name, *, serviced):
    return base_profile('neighbor' if name in NEIGHBOR_NAMES else name, serviced=serviced)
