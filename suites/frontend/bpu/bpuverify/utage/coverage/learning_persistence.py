"""Only complete bounded logical lifetimes may receive checked credit."""
from toffee import Bin, CoverGroupDef, CoverPointDef

from bpuverify.utage.model.learning_persistence import Program, PROFILES, MODES, RULES


def lifetime_coverage(status):
    keys = tuple(Program(profile, mode).label + '.' + rule
        for profile in PROFILES for mode in MODES for rule in RULES)
    definition = CoverGroupDef('utage_learning_persistence_v1',
        (CoverPointDef('obligation', {key: Bin.values(key) for key in keys}),))
    return definition.instantiate('kunminghu_v3.utage.learning-persistence.' + status)


class Coverage:
    def __init__(self, program):
        self.program, self.reached, self.closed = program, set(), False
        self.groups = {status: lifetime_coverage(status) for status in ('reached', 'checked')}

    def reach(self, rule, **witness):
        if self.closed or rule not in RULES or rule in self.reached:
            raise ValueError('one complete witness per declared obligation')
        self.groups['reached'].sample(dict(obligation=self.program.label + '.' + rule), metadata=witness)
        self.reached.add(rule)

    def finish(self):
        if self.closed or self.reached != set(RULES):
            raise AssertionError('incomplete learning/persistence cannot receive checked credit')
        for rule in RULES:
            self.groups['checked'].sample(dict(obligation=self.program.label + '.' + rule))
        self.closed = True
