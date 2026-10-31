"""Reuse original driver, version ledger and native SRAM/service monitor."""
from suites.frontend.bpu.utage.env.learning_persistence import Environment as Persistence,run as run_persistence
from suites.frontend.bpu.utage.model.predecessor_retention import PHASES


class Environment(Persistence):
    async def run(self):
        self.monitor.start()
        p,c = self.program,self.coverage
        before = None
        for phase in PHASES:
            await self.learn(phase,table=0,before_counter=before)
            before = p.counter(phase)
            if phase=='allocate':
                c.reach('distinct-predecessor-and-match-ancestors')
            if phase=='reward':
                c.reach('reward-survives-turnover')
            if phase=='saturated-reward':
                c.reach('saturated-learning-preserves-direction')
            if phase=='base-agreement':
                c.reach('base-agreement-preserves-protection')
        self.check(6*p.count,len(self.ledger.feedback),'all distinct predecessor feedbacks accepted exactly once')
        c.reach('real-original-feedback-once')
        c.reach('actual-versions-services-and-storage')
        native = self.monitor.latest_shadow[0]
        present = {cell['index'] for cell in native['cells'] if cell['valid']}
        expected = {p.identity(k,0)[1] for k in p.order(PHASES[-1])[-len(native['cells']):]}
        self.check(expected,present,'actual retained predecessor identities follow the declared capacity boundary')
        retired = [k for k in p.histories if p.identity(k,0)[1] not in present]
        self.check(max(0,p.count-len(native['cells'])),len(retired),'real first retirement or complete chronological turn')
        # These consumers cannot be satisfied by a retained shadow identity.
        # Each SRAM word and actual service was already checked independently.
        if retired:
            await self.queries(retired,table=0,counter=p.counter(PHASES[-1]))
        c.reach('declared-retention-and-SRAM-consumers',retired=len(retired))
        self.check(tuple(saved for _,saved in self.originals),tuple(source.meta for source,_ in self.originals),
            'all original predecessor metadata remain immutable')
        self.check(p.protection(PHASES[-1]),tuple(v.as_int() for v in self.monitor.protection.sample().counters),
            'all other short entries and the unlearned long table preserve protection')
        c.reach('all-neighbors-and-originals-preserved')
        self.agent.reference.raise_failure()
        self.evidence.update(retired_predecessors=retired,actual_retained_indices=sorted(present),
            matched_branch_is_not_read_predecessor=True,all_target_versions_actually_persistent=True)
        c.finish()


async def run(agent,program,coverage,evidence):
    await run_persistence(agent,program,coverage,evidence,environment_type=Environment)
