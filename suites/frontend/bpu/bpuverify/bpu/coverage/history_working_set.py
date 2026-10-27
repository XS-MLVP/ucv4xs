"""History lifetime obligations; no bank/set cross-product."""
import json
import os
from pathlib import Path
from time import monotonic

from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase

from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.model.history_working_set import (PROFILES, RULES, MAINTENANCE_RULES,
    SHORT_PROFILES,SHORT_RULES,SHORT_MIXED_PROFILES,SHORT_MIXED_RULES)


class HistoryWorkingSetCoverage:
    def __init__(self, program):
        self.program, self.evidence = program,None
        self.started = monotonic()
        destination = os.environ.get('BPUVERIFY_HISTORY_PROGRESS_DIR')
        self.progress_path = None
        if destination:
            root = Path(__file__).resolve().parents[3]/'results'
            directory = Path(destination).resolve()
            if not directory.is_relative_to(root) or directory == root or not directory.is_dir():
                raise ValueError('optional history progress requires an existing run directory under results/')
            self.progress_path = directory/f'history-progress-analysis-{program.profile}.json'
        keys = tuple(f'{profile}.{rule}' for profile in PROFILES for rule in RULES)
        self.groups = {status:CoverGroupDef('bpu_real_history_working_set_v2',(
            CoverPointDef('obligation',{key:Bin.values(key) for key in keys}),
        )).instantiate('kunminghu_v3.bpu.history-working-set.direction-lifetime.'+status) for status in ('reached','checked')}
        self.maintenance_groups = {status:CoverGroupDef('bpu_real_history_maintenance_v1',(
            CoverPointDef('obligation',{rule:Bin.values(rule) for rule in MAINTENANCE_RULES}),
        )).instantiate('kunminghu_v3.bpu.history-working-set.maintenance.'+status) for status in ('reached','checked')}

    def record(self, status, rule, **witness):
        if rule not in RULES:raise ValueError('unknown real history lifetime obligation')
        self.groups[status].sample(dict(obligation=self.program.profile+'.'+rule),metadata=witness)

    def write(self, output):
        write_functional_coverage(CoverageDatabase((*self.groups.values(),*self.maintenance_groups.values())),
                                  output/'functional-coverage-real-history-working-set.json')

    def maintenance(self, status, rule, **witness):
        if rule not in MAINTENANCE_RULES:raise ValueError('unknown history maintenance obligation')
        self.maintenance_groups[status].sample(dict(obligation=rule),metadata=witness)

    def attach_evidence(self, properties):
        if self.evidence is not None:
            properties.append(('real_history_working_set',json.dumps(self.evidence,ensure_ascii=False)))

    def progress(self, checks):
        """Optional one-file diagnostic, never a per-cycle/source journal."""
        if self.progress_path is None:return
        data = dict(profile=self.program.profile,phase=checks.phase,
            elapsed_seconds=monotonic()-self.started,
            actual_source_windows=checks.path_captures,actual_feedback=len(checks.feedback_receipts),
            actual_recoveries=checks.path_recoveries,declared_histories=len(self.program.paths),
            admitted=len(checks.admitted),revisited=len(checks.revisited),
            penalized=len(checks.penalized),recovered=len(checks.recovered),
            compared_cycles=checks.counter_comparisons//1024,
            maintenance_epochs=checks.maintenance.failures.ages,
            maintenance_confirmed=len(checks.maintenance.receipts),
            completed_obligations=sorted(checks.completed))
        self.progress_path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def short_path_retention_coverage(status):
    if status not in ('reached','checked'):
        raise ValueError('declared short retention lifecycle required')
    return CoverGroupDef('bpu_short_path_retention_v1',(CoverPointDef('obligation',
        {profile+'.'+rule:Bin.values(profile+'.'+rule) for profile in SHORT_PROFILES for rule in SHORT_RULES}),
        )).instantiate('kunminghu_v3.bpu.short-path-retention.'+status)


class ShortPathRetentionCoverage(HistoryWorkingSetCoverage):
    rules=SHORT_RULES
    factory=staticmethod(short_path_retention_coverage)
    output_name='functional-coverage-short-path-retention.json'
    property_name='semantic_bpu_short_path_retention'

    def __init__(self,program):
        self.program,self.evidence=program,None
        self.started,self.progress_path=monotonic(),None
        self.groups={status:self.factory(status) for status in ('reached','checked')}
        self.maintenance_groups={}

    def record(self,status,rule,**witness):
        if rule not in self.rules:
            raise ValueError('declared short-path semantic obligation required')
        self.groups[status].sample(dict(obligation=self.program.profile+'.'+rule),metadata=witness)

    def maintenance(self,*args,**kwargs):
        raise AssertionError('global maintenance is not declared by this short retention program')

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()),output/self.output_name)

    def attach_evidence(self,properties):
        if self.evidence is not None:
            properties.append((self.property_name,json.dumps(self.evidence,ensure_ascii=False)))


def short_path_mixed_coverage(status):
    if status not in ('reached','checked'):raise ValueError('declared mixed short lifetime status required')
    return CoverGroupDef('bpu_short_path_mixed_v1',(CoverPointDef('obligation',
        {profile+'.'+rule:Bin.values(profile+'.'+rule) for profile in SHORT_MIXED_PROFILES for rule in SHORT_MIXED_RULES}),
        )).instantiate('kunminghu_v3.bpu.short-path-mixed.'+status)


class ShortMixedPathCoverage(ShortPathRetentionCoverage):
    rules=SHORT_MIXED_RULES
    factory=staticmethod(short_path_mixed_coverage)
    output_name='functional-coverage-short-path-mixed.json'
    property_name='semantic_bpu_short_path_mixed'
