"""Real resolves change Main; continuous source-qualified flow biases Ahead."""
from bpuverify.bpu.env.early_direction import EarlyDirectionProgram
from bpuverify.bpu.model.early_opposition import ahead_owner,main_counter,is_opposed,stable_negative,steady_history,CONDITIONAL,FALLBACK
from bpuverify.bpu.transaction.types import BpuBranchFeedback


class EarlyOppositionProgram(EarlyDirectionProgram):
    fallback_position = FALLBACK
    def __init__(self,*args):
        super().__init__(*args)
        self.owners=[]

    async def query(self,source):
        result=await super().query(source);self.owners.append(result);return result

    async def consume(self,name,predicate):
        result=await super().consume(name,predicate);self.owners.append(result);return result

    async def steer_main(self,source,goal):
        if goal not in (0,3):raise ValueError('the opposed-base program steers to a semantic saturation endpoint')
        await self.pause()
        await self.agent.configure_predictors(abtb=False,settle=True)
        source=await self.query(source)
        # At most three real events are needed for a two-bit direction
        # counter. These are independent resolutions, not settling cycles.
        for _ in range(4):
            token=self.checker.source_token(source);counter=main_counter(token)
            if counter==goal:
                await self.restart(source)
                return await self.consume('owned_Main_only_steady_path',lambda token:
                    main_counter(token)==goal and steady_history(token,CONDITIONAL if goal else FALLBACK))
            taken=counter<goal
            await self.resolve(source,BpuBranchFeedback(CONDITIONAL,self.pc,1,taken=int(taken),
                mispredict=int((counter>=2)!=taken)),retire=False)
            source=await self.query(source)
        raise AssertionError('owned Main counter did not reach the declared saturation endpoint')

    async def strong_negative(self,source):
        await self.restart(source)
        return await self.consume('strong_owned_negative_provider',lambda token:stable_negative(self.checker.model.sources,token))

    async def positive_base(self,source,protected):
        await self.pause()
        await self.agent.configure_predictors(abtb=True,settle=True)
        await self.restart(source)
        def positive(token):
            sources=self.checker.model.sources;owner=ahead_owner(sources,token)
            frame=sources.short_snapshot(token).prediction.frame
            return (main_counter(token)==3 and steady_history(token,CONDITIONAL) and owner is not None and owner[1]==3 and frame is not None
                and frame.read.indices[protected[0]]!=protected[1])
        return await self.consume('same_ahead_owner_positive_from_other_history',positive)

    async def opposed(self,source,checks):
        await self.pause()
        await self.agent.configure_predictors(abtb=True,settle=True)
        await self.restart(source)
        result=await self.consume('actual_opposed_early_consumer',lambda token:is_opposed(self.checker.model.sources,token))
        checks.opposed_consumer(result)
        await self.observation.wait('actual_useful_increase_from_owned_opposed_source',lambda _:
            bool(checks.confirmed_increases) and checks.pending_effect is None)
        return result
