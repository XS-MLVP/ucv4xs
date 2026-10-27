"""Normal preparation and response draining; no pin or edge operations."""
from copy import deepcopy
from dataclasses import replace

from bpuverify.utage.model.source_ownership import POSITION
from bpuverify.utage.transaction.types import UtageTraining


class SourceOwnershipEnv:
    def __init__(self, agent, checks):
        self.agent, self.checks = agent, checks
        self.originals = []

    def remember(self, prediction):
        self.originals.append((prediction, deepcopy(prediction.meta)))
        return prediction

    async def read(self, profile, base=1):
        actual = self.remember(await self.agent.predict(profile.pc, POSITION, base, folded_history=profile.history))
        self.checks.profile(profile, actual, base)
        return actual

    async def prepare(self, profiles):
        await self.agent.reset()
        sources = {}
        for profile in profiles:
            if profile.counter is None: continue
            base = 1-profile.taken
            cold = await self.read(replace(profile, counter=None), base)
            await self.agent.train(UtageTraining(profile.pc, POSITION, profile.taken, cold.meta))
            weak = replace(profile, counter=4 if profile.taken else 3)
            current = await self.read(weak, base)
            if weak.counter != profile.counter:
                self.checks.check(1, abs(profile.counter-weak.counter), 'one declared preparation reinforcement')
                await self.agent.train(UtageTraining(profile.pc, POSITION, profile.taken, current.meta, mispredict=0))
                current = await self.read(profile, base)
            sources[profile.name] = current
        return sources

    async def burst(self, sequence):
        transfers = tuple(self.agent.submit_predict(p.pc, POSITION, base, folded_history=p.history)
                          for p, base in sequence)
        await self.agent.drain_predictions()
        actuals = tuple([self.remember(await transfer) for transfer in transfers])
        return transfers, actuals

    async def consumers(self, profiles, rule):
        self.checks.begin(rule)
        for profile in profiles: await self.read(profile)
        self.agent.reference.raise_failure()
        self.checks.end(rule)
