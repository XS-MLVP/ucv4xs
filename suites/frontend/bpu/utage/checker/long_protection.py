"""Check both provider effects, not merely the final long prediction."""
from toffee import Scoreboard
from suites.frontend.bpu.utage.checker.selective_protection import Checks as SelectiveChecks
from suites.frontend.bpu.utage.model.long_protection import SHADOW_CAPACITY


class Checks(SelectiveChecks):
    def __init__(self,program):
        super().__init__(program);self.board=Scoreboard('utage.long-provider-owned-protection')

    def prefix(self,monitor,count):
        if monitor.failure is not None:raise monitor.failure
        self.check(count,len(monitor.records),'all original learning boundaries are observed exactly once')
        sequences=[sum(table in step.tables for step in self.program.steps[:self.compared]) for table in (0,1)]
        for step,row in zip(self.program.steps[self.compared:count],monitor.records[self.compared:count],strict=True):
            self.check(False,row['aged'],'highest-provider failures below maintenance threshold do not invent aging')
            self.check(step.changes,row['changes'],'only declared original identities change protection, including both promotion effects')
            self.check(set(map(str,step.tables)),set(row['versions']),'promotion learns both providers; later long feedback never rewrites short experience')
            for table in step.tables:
                actual=row['versions'][str(table)];sequence=sequences[table]
                self.check((sequence,8,(sequence+1)%8),(actual['sequence'],actual['depth'],actual['next']),
                    'every retained version advances the actual provider chronology')
                self.check(step.cell(table),actual['new_cell'],'complete retained identity, direction and provider belong to original feedback')
                sequences[table]+=1
        self.compared=count
        self.check(self.program.protection_after(count),monitor.all_protection(),
            'all protection cells remain the reset-derived logical state at every learning prefix')

    def consumer_lifetime(self,monitor):
        snapshot=monitor.long_snapshot
        self.check(True,snapshot is not None,'real long-cache observation required before final consumers')
        resident={cell['index'] for cell in snapshot['cells'] if cell['valid']}
        owners={self.program.read_indices(owner)[1] for owner in (0,1)}
        departed=self.program.lifetime=='after-unrelated-version-turnover'
        self.check(set() if departed else owners,resident&owners,
            'declared consumer uses retained versions or follows complete target cache departure')
        self.check(len(self.program.steps),self.compared,'departure cannot replace missing original learning effects')
        if departed:
            suffix=tuple(step for step in self.program.steps if step.owner==2)
            self.check({2},{step.owner for step in suffix},'only unrelated original feedback causes cache turnover')
            self.check(SHADOW_CAPACITY,sum(1 in step.tables for step in suffix),'one complete retained-version capacity is replaced')
        return dict(tick=snapshot['tick'],target_indices=sorted(owners),resident_indices=sorted(resident),
            all_targets_absent=departed,no_target_relearning=True,depth=len(snapshot['cells']))
