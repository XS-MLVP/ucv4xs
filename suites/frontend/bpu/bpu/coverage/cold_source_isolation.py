"""Actual cold launch, original feedback and consumer obligations."""
import json

from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from suites.frontend.bpu.bpu.model.cold_source_isolation import SOURCES, MODES, RULES


class ColdSourceCoverage:
    def __init__(self, program):
        self.program, self.evidence = program, None
        self.reached = set()
        keys = tuple(f'{source}.{mode}.{rule}' for source in SOURCES for mode in MODES for rule in RULES)
        self.groups = {status: CoverGroupDef('bpu_cold_source_isolation_v1', (
            CoverPointDef('obligation', {key:Bin.values(key) for key in keys}),
        )).instantiate('kunminghu_v3.bpu.cold-source-isolation.'+status) for status in ('reached','checked')}

    def record(self, status, rule, **witness):
        if rule not in RULES: raise ValueError('unknown cold source isolation obligation')
        self.groups[status].sample(dict(obligation=f'{self.program.source}.{self.program.mode}.{rule}'), metadata=witness)
        if status == 'reached': self.reached.add(rule)

    def observe_launch(self, enabled, initialized, tick):
        index = 0 if self.program.source == 'ubtb' else 3
        if initialized and not enabled[index] and RULES[0] not in self.reached:
            self.record('reached',RULES[0],actual_tick=tick)

    def write(self, output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/'functional-coverage-cold-source-isolation.json')

    def attach_evidence(self, properties):
        if self.evidence is not None:
            properties.append(('cold_source_isolation',json.dumps(self.evidence,ensure_ascii=False)))
