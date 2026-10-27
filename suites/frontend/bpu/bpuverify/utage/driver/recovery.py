"""Compound snapshot protocol, using public input-only Reactor transfers."""
from bpuverify.utage.transaction.types import UtageLookup
from bpuverify.utage.model.source_ownership import POSITION


class RecoveryDriver:
    # The lookup adapter has two downstream upstream-result metadata phases.
    # This supplies valid base descriptors through them; it is not a settling
    # delay or a response selected by waiting an arbitrary number of cycles.
    METADATA_PHASES = 2

    def __init__(self, agent): self.agent = agent

    async def send(self, program, feedback=None):
        await self.agent.drain_predictions()
        requests = tuple(UtageLookup(p.pc, POSITION, 1, folded_history=p.history) for p in program.profiles)
        requests += (UtageLookup(program.target.pc, POSITION, 1, override=program.stage,
            override_pc=program.target.pc, folded_history=program.history,
            index_pc=program.decoy.pc, index_history=program.decoy.history),)
        # send() queues immediately and completes at acceptance, not response.
        # These are protocol input beats, not uncancellable normal-query promises.
        launched = tuple(self.agent.lookup_driver.send(request) for request in requests)
        metadata = tuple(self.agent.result_driver.send(requests[0])
                         for _ in range(len(requests) + self.METADATA_PHASES))
        if feedback is not None: await self.agent.train(feedback)
        accepted = tuple([await transfer for transfer in launched])
        for transfer in metadata: await transfer
        self.agent.reference.raise_failure()
        return accepted
