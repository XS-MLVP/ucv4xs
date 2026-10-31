"""A bounded, input-only recovery protocol; no normal promise is cancelled."""
from suites.frontend.bpu.utage.driver.recovery import RecoveryDriver
from suites.frontend.bpu.utage.transaction.types import UtageLookup, UtageBaseBranch


class SavedVectorDriver:
    def __init__(self,agent): self.agent=agent

    async def send(self,program,feedback=None):
        await self.agent.drain_predictions()
        branches=tuple(None if p is None else UtageBaseBranch(p,int(p==2)) for p in program.positions())
        requests=tuple(UtageLookup(p.pc,0,0,folded_history=p.history,branches=branches) for p in program.profiles)
        requests+=(UtageLookup(program.target.pc,0,0,override=program.stage,override_pc=program.target.pc,
            folded_history=program.history,branches=branches,index_pc=program.decoy.pc,index_history=program.decoy.history),)
        launched=tuple(self.agent.lookup_driver.send(request) for request in requests)
        metadata=tuple(self.agent.result_driver.send(requests[0])
            for _ in range(len(requests)+RecoveryDriver.METADATA_PHASES))
        if feedback is not None: await self.agent.train(feedback)
        for transfer in launched: await transfer
        for transfer in metadata: await transfer
        self.agent.reference.raise_failure()
        return launched
