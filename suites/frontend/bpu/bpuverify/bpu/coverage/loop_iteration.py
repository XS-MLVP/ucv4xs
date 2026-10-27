"""Semantic iteration/version obligations; pure model cycles earn no DUT credit."""
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.model.loop_iteration import PROGRAMS

RULES = ('nonzero-original-loop-source-owned', 'younger-natural-speculation-saturates',
         'stalled-loop-context-and-original-held', 'actual-recovery-uses-original-version',
         'recovery-lookup-and-registered-state-compared', 'fresh-public-consumer-compared',
         'original-public-metadata-remains-immutable', 'normal-pipeline-repair-iteration-compared')
FINAL_RULES = ('normal-weak-provider-and-opposite-base-qualified',
    'actual-final-repair-owns-iteration-source', 'repair-lookup-and-registered-state-compared',
    'exact-repair-issued-public-consumer-compared', 'original-public-snapshots-preserved')


class LoopIterationCoverage:
    def __init__(self, program):
        if program not in PROGRAMS:
            raise ValueError('unknown iteration program')
        self.groups = {status: CoverGroupDef('bpu_owned_loop_iteration_v1', (
            CoverPointDef('rule', {r: Bin.values(r) for r in RULES}),)).instantiate(
                f'kunminghu_v3.bpu.owned-loop-iteration.{program.name}.{status}')
            for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        if status not in self.groups or rule not in RULES:
            raise ValueError('unknown iteration evidence role or rule')
        self.groups[status].sample(dict(rule=rule), metadata=witness)

    def finish(self):
        for group in self.groups.values():
            group.assert_coverage(100)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-loop-iteration.json')


class FinalIterationCoverage(LoopIterationCoverage):
    def __init__(self):
        self.groups = {status: CoverGroupDef('bpu_final_loop_iteration_v1', (
            CoverPointDef('rule', {r: Bin.values(r) for r in FINAL_RULES}),)).instantiate(
                f'kunminghu_v3.bpu.owned-loop-iteration.final-direction-repair.{status}')
            for status in ('reached', 'checked')}

    def record(self, status, rule, **witness):
        if status not in self.groups or rule not in FINAL_RULES:
            raise ValueError('unknown final-iteration evidence role or rule')
        self.groups[status].sample(dict(rule=rule), metadata=witness)
