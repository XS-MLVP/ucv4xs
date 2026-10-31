"""Normal public preparation and batches; existing drivers own all scheduling."""
from contextlib import asynccontextmanager
from copy import deepcopy
from suites.frontend.bpu.utage.checker.checking import UtageUsefulChecker
from suites.frontend.bpu.utage.checker.long_history_learning import LongHistoryLearningChecks
from suites.frontend.bpu.utage.model.long_history_learning import PC, POSITION, HISTORIES, address
from suites.frontend.bpu.utage.transaction.types import UtageTraining


class LongHistoryLearningEnv:
    def __init__(self, agent, mode, coverage, monitor):
        self.agent,self.mode,self.monitor = agent,mode,monitor
        self.checks = LongHistoryLearningChecks(mode,coverage)
        self.read_sources = {}

    async def read(self, path, base, *, table=1, counter=None):
        transfer = self.agent.submit_predict(PC,POSITION,base,folded_history=HISTORIES[path])
        prediction = await transfer
        self.agent.reference.raise_failure()
        self.checks.response(path,prediction,base,table=table,counter=counter)
        self.read_sources[id(prediction)] = transfer
        return prediction

    async def send(self, transactions, phase):
        self.monitor.plan(transactions,phase=phase)
        if self.mode=='adjacent': await self.agent.train_many(transactions)
        else:
            for transaction in transactions: await self.agent.train(transaction)
        self.monitor.finish_phase()

    async def teach(self, source, actual, phase):
        await self.send((UtageTraining(PC,POSITION,actual,deepcopy(source.meta)),),phase)

    async def prepare(self):
        cold = await self.read('a',0)
        await self.teach(cold,1,'shared short allocation')
        short = await self.read('a',1,table=0,counter=4)
        await self.teach(short,0,'negative long path allocation')
        inherited = await self.read('b',1,table=0,counter=3)
        await self.teach(inherited,1,'positive long path allocation')
        await self.read('a',1,counter=3); await self.read('b',0,counter=4)
        await self.invariants()
        self.agent.check_useful(1,address('a')[1],2); self.agent.check_useful(1,address('b')[1],2)
        self.checks.reach('prepared-distinct-long-paths',short_index=address('a')[0],
                          paths={p:dict(index=address(p)[1],counter=s.counter,protection=s.useful)
                                 for p,s in self.checks.ledger.states.items()})

    async def capture(self, paths):
        transfers = tuple(self.agent.submit_predict(PC,POSITION,int(p=='a'),folded_history=HISTORIES[p]) for p in paths)
        await self.agent.drain_predictions()
        predictions = tuple([await transfer for transfer in transfers])
        owners = self.checks.capture(paths,transfers,predictions)
        return tuple(zip(owners,predictions,strict=True))

    async def batch(self, sources, directions, rule):
        batch = tuple((owner,actual) for (owner,_),actual in zip(sources,directions,strict=True))
        _,states = self.checks.ledger.preview(batch)
        transactions = tuple(UtageTraining(PC,POSITION,actual,deepcopy(source.meta),
            mispredict=int(source.taken!=actual)) for (_,source),actual in zip(sources,directions,strict=True))
        first = len(self.monitor.accepted_feedback)
        await self.send(transactions,rule)
        confirmation = self.monitor.reference.last_tick
        # Consumers also make direction forwarding independently observable.
        consumers = {}
        for path,state in states.items():
            prediction = await self.read(path,int(path=='a'),counter=state.counter)
            consumers[path] = self.read_sources[id(prediction)],prediction
        await self.invariants()
        summary = self.monitor.summary()
        self.checks.verified_phase(rule,batch,self.monitor.accepted_feedback[first:],
            tuple(self.monitor._payload(t) for t in transactions),tuple(summary['final_actual']),
            consumers,tick=confirmation,cycle_ticks=self.monitor.reference.cycle_ticks)

    async def invariants(self):
        await self.read('fallback',0,table=0,counter=4)
        self.agent.check_useful(0,address('fallback')[0],0)
        self.checks.reach('shared-short-fallback',counter=4,protection=0,index=address('fallback')[0])
        await self.read('cold',1)
        self.checks.reach('cold-neighbor-isolation',indices=address('cold'))


@asynccontextmanager
async def long_history_learning_env(agent, mode, coverage):
    await agent.reset()
    monitor = UtageUsefulChecker(mode=mode,scope=dict(program='long-history-learning',histories=HISTORIES))
    async with agent.observe_useful(monitor):
        yield LongHistoryLearningEnv(agent,mode,coverage,monitor)
