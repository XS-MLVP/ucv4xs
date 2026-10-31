"""Semantic return recovery boundaries; no physical-coordinate coverage axes."""

from suites.frontend.bpu.coverage.exports import write_functional_coverage
from toffee import Bin,CoverGroupDef,CoverPointDef,CoverageDatabase

from suites.frontend.bpu.bpu.coverage.ras_redo import REGISTERED_EFFECT_TICK_DELTA


STORAGES = ('speculative','retained')
RULES = {
    8:('restore-repeat-pop','younger-returns-restored','predecessor-owned','redo-retired-once',
       'return-target-owned','surviving-frame-intact'),
    9:('restore-group-pop','younger-returns-restored','predecessor-owned','redo-retired-once',
       'return-target-owned','surviving-frame-intact'),
}


def return_recovery_coverage(calls,storage,status):
    if calls not in RULES or storage not in STORAGES or status not in ('reached','checked'):
        raise ValueError('unknown return recovery scope')
    return CoverGroupDef(f'bpu_ras_return_recovery_{calls}_v1',(
        CoverPointDef('rule',{rule:Bin.values(rule) for rule in RULES[calls]}),
    )).instantiate(f'kunminghu_v3.bpu.ras-return-recovery.{calls}.{storage}.{status}',
        contract='owned real return checkpoint -> prefix restored then pop -> exact registered effect and surviving consumer')


class ReturnRecoveryCoverage:
    def __init__(self,calls,storage):
        self.calls,self.storage = calls,storage
        self.groups = {status:return_recovery_coverage(calls,storage,status) for status in ('reached','checked')}
        self.reset()

    def reset(self):
        self.pending = []
        self.recovery_key = None
        self.recovery_checked = False
        self.redo_retirements = 0

    def record(self,status,rule,tick):
        if rule in ('return-target-owned','surviving-frame-intact') and not self.recovery_checked:
            return
        self.groups[status].sample(dict(rule=rule),metadata=dict(rule=rule,tick=tick))

    def accept(self,events,model,tick):
        if events.reset:
            self.reset()
            return
        if not events.enabled:
            return
        recovery = events.recovery
        rules,effects = [],{}
        if recovery is not None and recovery.action==1:
            prefix = model.checkpoints.get((recovery.group,recovery.calls,recovery.repeat))
            if prefix is not None and prefix.calls==self.calls and prefix.head.repeat==(self.calls-1)%8:
                predecessor = prefix.frames[-2]
                storage = 'speculative' if model._live(predecessor,prefix) else 'retained'
                if storage!=self.storage:
                    raise AssertionError(f'return predecessor lifetime: expected {self.storage}, owned {storage}')
                rules.extend(('restore-repeat-pop' if self.calls==8 else 'restore-group-pop','predecessor-owned'))
                if len(prefix.frames)-1>len(model.program.frames):
                    rules.append('younger-returns-restored')
                self.recovery_key = prefix.redirect_key()
                effects = dict(recovery=('recovery',1,None),depth=len(prefix.frames)-2)
        if (events.retirement is not None and model.pending_retirement is not None
                and self.recovery_key is not None and model.pending_retirement.action==1
                and model.pending_retirement.before.redirect_key()==self.recovery_key):
            self.redo_retirements += 1
            if self.redo_retirements!=1:
                raise AssertionError('redone return retired more than once')
            rules.append('redo-retired-once')
            effects['retirements'] = model.retirements+1
        for rule in rules:
            self.record('reached',rule,tick)
        if rules:
            self.pending.append((tick+REGISTERED_EFFECT_TICK_DELTA,tuple(rules),effects))

    def consume(self,tick,model):
        remaining = []
        for due,rules,effects in self.pending:
            if due<tick:
                raise AssertionError(f'return recovery missed its exact comparison: due={due}, tick={tick}')
            if due==tick:
                if ('recovery' in effects and (model.last_applied!=effects['recovery']
                        or len(model.program.frames)-1!=effects['depth'])
                        or 'retirements' in effects and model.retirements!=effects['retirements']):
                    raise AssertionError(f'return recovery has no accepted registered effect: {effects!r}, state={model.state()!r}')
                for rule in rules:
                    self.record('checked',rule,tick)
                if 'recovery' in effects:
                    self.recovery_checked = True
            else:
                remaining.append((due,rules,effects))
        self.pending = remaining

    def finish(self):
        if self.pending:
            raise AssertionError(f'return recovery events lack effect comparisons: {self.pending!r}')
        for group in self.groups.values():
            group.assert_coverage(100)

    def write(self,output):
        write_functional_coverage(CoverageDatabase(self.groups.values()), output/f'functional-coverage-ras-return-recovery-{self.calls}-{self.storage}.json')
