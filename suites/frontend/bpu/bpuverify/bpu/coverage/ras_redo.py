"""Recovery/redo and repeated-return events at the compression boundary."""

from bpuverify.common.coverage.exports import write_functional_coverage
from toffee import Bin, CoverGroupDef, CoverPointDef, CoverageDatabase


RULES = {
    8:('redo-repeat-step','younger-suffix-flushed','redo-retired-once','return-repeat-decrement',
       'return-target-owned','surviving-frame-intact'),
    9:('redo-group-split','younger-suffix-flushed','redo-retired-once','return-crosses-group',
       'return-repeat-decrement','return-target-owned','surviving-frame-intact'),
}

# Component DriveStable input -> one registered cycle -> Rising comparison.
# These are reactor ticks (two per cycle), not a settling delay for stimulus.
REGISTERED_EFFECT_TICK_DELTA = 3


def redo_coverage(calls,status):
    if calls not in RULES or status not in ('reached','checked'):
        raise ValueError('unknown RAS redo boundary/status')
    return CoverGroupDef(f'bpu_ras_redo_boundary_{calls}_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES[calls]}),
    )).instantiate(f'kunminghu_v3.bpu.ras-redo.{calls}.{status}',
        contract='actual owned recovery/retirement -> independent program and groups -> exact effect/consumer comparison')


class RedoCoverage:
    def __init__(self,calls):
        self.calls = calls
        self.groups = {status:redo_coverage(calls,status) for status in ('reached','checked')}
        self.pending = []
        self.recovery_key = None
        self.redo_retirements = 0

    def record(self,status,rule,tick):
        self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,tick=tick))

    def accept(self,events,model,tick):
        if events.reset:
            self.pending.clear()
            self.recovery_key = None
            self.redo_retirements = 0
            return
        if not events.enabled:
            return
        rules = []
        effects = {}
        recovery = events.recovery
        if recovery is not None and recovery.action==2:
            source = model.checkpoints.get((recovery.group,recovery.calls,recovery.repeat))
            if source is not None and source.calls==self.calls-1 and source.head.repeat==(self.calls-2)%8:
                rules.append('redo-repeat-step' if self.calls==8 else 'redo-group-split')
                if model.program.calls>self.calls:
                    rules.append('younger-suffix-flushed')
                self.recovery_key = source.commit_key()
                effects['recovery'] = ('recovery',recovery.action,recovery.address)
        if events.retirement is not None and model.pending_retirement is not None:
            operation = model.pending_retirement
            if operation.action==2 and self.recovery_key is not None and operation.before.commit_key()==self.recovery_key:
                self.redo_retirements += 1
                if self.redo_retirements!=1:
                    raise AssertionError(f'redone call retired more than once: {self.recovery_key}')
                rules.append('redo-retired-once')
                effects['retirements'] = model.retirements+1
            elif operation.action==1:
                # advance() already applied the preceding registered commit,
                # so this view includes same-cycle forwarding for adjacent returns.
                group = operation.before.head.group%8
                if model.committed[group].repeat:
                    rules.append('return-repeat-decrement')
                    effects['retirements'] = model.retirements+1
                elif self.calls==9 and group==2:
                    rules.append('return-crosses-group')
                    effects['retirements'] = model.retirements+1
        for rule in rules:
            self.record('reached',rule,tick)
        if rules:
            self.pending.append((tick+REGISTERED_EFFECT_TICK_DELTA,tuple(rules),effects))

    def consume(self,tick,model):
        remaining = []
        for due,rules,effects in self.pending:
            if due<tick:
                raise AssertionError(f'RAS boundary effect missed its exact comparison: due={due}, tick={tick}')
            if due==tick:
                if ('recovery' in effects and model.last_applied!=effects['recovery']
                        or 'retirements' in effects and model.retirements!=effects['retirements']):
                    raise AssertionError(f'RAS boundary input had no accepted registered effect: {effects!r}, state={model.state()!r}')
                for rule in rules:
                    self.record('checked',rule,tick)
            else:
                remaining.append((due,rules,effects))
        self.pending = remaining

    def finish(self):
        if self.pending:
            raise AssertionError(f'RAS boundary events have no effect comparison: {self.pending!r}')
        for group in self.groups.values():
            group.assert_coverage(100)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/f'functional-coverage-ras-redo-{self.calls}.json')
