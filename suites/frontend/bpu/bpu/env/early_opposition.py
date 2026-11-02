"""Real resolves change Main; continuous source-qualified flow biases Ahead."""
from suites.frontend.bpu.bpu.env.early_direction import EarlyDirectionProgram
from suites.frontend.bpu.bpu.model.early_opposition import ahead_owner,main_counter,is_opposed,stable_negative,steady_history,CONDITIONAL,FALLBACK
from suites.frontend.bpu.bpu.transaction.types import BpuBranchFeedback
from suites.frontend.bpu.bpu.driver.recovery import RecoveryDriver
from suites.frontend.bpu.bpu.model.entry_protection import INITIALIZATION_ROUNDS, INITIALIZATION_REQUESTS_PER_ROUND


class EarlyOppositionProgram(EarlyDirectionProgram):
    fallback_position = FALLBACK
    def __init__(self,*args):
        super().__init__(*args)
        self.owners=[]

    async def query(self,source):
        result=await super().query(source);self.owners.append(result);return result

    async def consume(self,name,predicate):
        result=await super().consume(name,predicate);self.owners.append(result);return result

    async def _one_original(self,*,recover=None):
        """One actual S1 owner, full S3/learning drain, existing driver ownership."""
        await self.pause()
        selection=self.checker.admission
        window=selection.arm(self.pc,1,available=1,requires_preparation=False)
        try:
            if recover is None:
                event=await self.agent.accept_predictions_until(window.accepted,
                    name='owned-original-single-input',failure=lambda:self.checker.failure)
            else:
                await RecoveryDriver(self.agent,self.checker).send(recover,
                    position=(self.pc//16)*16+self.fallback_position-self.pc,
                    branch_type=2,until=window.accepted)
                event=window.accepted.result()
            ((tick,sequence),)=selection.finish(window,event)
            source=await self.agent.next_transaction(start_pc=self.pc,after_tick=tick-1)
            if self.checker.source_token(source).sequence!=sequence:
                raise AssertionError('single-input scope lost the exact accepted original')
            await self.pause()
            self.owners.append(source)
            return source
        finally:
            selection.cancel(window)

    async def bounded_opposition(self,source,checks):
        await self.pause()
        await self.agent.configure_predictors(abtb=True,settle=True)
        for _ in range(8):
            source=await self._one_original(recover=source)
            source=await self._one_original()
            if is_opposed(self.checker.model.sources,self.checker.source_token(source)):
                checks.opposed_consumer(source)
                await self.observation.wait('actual_useful_increase_from_bounded_opposed_source',lambda _:
                    bool(checks.confirmed_increases) and checks.pending_effect is None)
                return source
        raise AssertionError('bounded owned opposition did not become qualified')

    async def prepare_short_initialization(self):
        await self.pause()
        await self.agent.configure_predictors(abtb=False,settle=True)

    async def initialize_short_negative(self,source):
        await self.restart(source)
        source=await self.consume('short_initialization_Main_only_steady_fallback',
            lambda token:steady_history(token,FALLBACK))
        await self.agent.configure_predictors(abtb=True,settle=True)
        initialization=[]
        for _ in range(INITIALIZATION_ROUNDS):
            for index in range(INITIALIZATION_REQUESTS_PER_ROUND):
                source=await self._one_original(recover=source if index==0 else None)
                token=self.checker.source_token(source)
                initialization.append(dict(tick=source.prediction_tick,owner=token.sequence,
                    history=token.history.history%512,
                    snapshot=self.checker.model.sources.short_snapshot(token),
                    learning=self.checker.model.sources.short.state()))
        self.initialization=initialization
        return source

    async def bounded_strong_negative(self,source):
        for index in range(INITIALIZATION_REQUESTS_PER_ROUND):
            source=await self._one_original(recover=source if index==0 else None)
        if not stable_negative(self.checker.model.sources,self.checker.source_token(source)):
            raise AssertionError('bounded short preparation did not deliver its fresh stable NT0 original')
        return source

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
