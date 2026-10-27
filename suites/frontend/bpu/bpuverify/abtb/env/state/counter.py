"""bpuverify.abtb.env.state.counter components."""

from bpuverify.common.coverage.exports import write_functional_coverage

from bpuverify.common.env.artifacts import output_path
from copy import deepcopy
from dataclasses import asdict
from dataclasses import replace
from bpuverify.common.env.trace import dump_trace
from toffee import CoverageDatabase
from bpuverify.abtb.transaction.types import AbtbTraining
from bpuverify.abtb.case.state.vectors import same_pc_position_vectors
from bpuverify.abtb.model.state.counter import index
from bpuverify.abtb.model.state.counter import TRANSITIONS
from bpuverify.abtb.model.state.counter import victim
from bpuverify.abtb.checker.state.counter import CounterChecker
from bpuverify.abtb.monitor.state.counter import CounterMonitor
from bpuverify.abtb.coverage.state.supplemental import transition_coverage
from bpuverify.abtb.coverage.state.supplemental import gate_coverage
from bpuverify.abtb.env.state.session import StateObservation
from bpuverify.abtb.case.state.scope import bank_index
from bpuverify.abtb.case.state.scope import set_axis
from bpuverify.abtb.case.state.counter import packed


class CounterScenario:
    def __init__(self,agent,output,*,bank,sets):
        self.agent,self.output,self.bank,self.sets=agent,output,bank_index(bank),set_axis(sets)
        self.coverage=transition_coverage(bank,self.sets)
        self.gates=gate_coverage(bank,self.sets)
        self.checker=CounterChecker(scope=f'full-counter-grid-bank{bank}',coverage=self.coverage)
        self.monitor=CounterMonitor(agent)
        self.observation=StateObservation(agent,self.monitor,self.checker)
        self.known={}
        self.profiles=[]
        self.completed_sets=[]
        self.intents=[]
        self.metadata_ticks={}
        self.metadata_sources=[]

    async def __aenter__(self):
        await self.observation.__aenter__()
        return self

    async def __aexit__(self,exc_type,exc,traceback):
        await self.observation.__aexit__(exc_type,exc,traceback)
        report=dict(bank=self.bank,sets=list(self.sets),completed_sets=self.completed_sets,
            intents=self.intents,profiles=self.profiles,metadata_sources=self.metadata_sources,
            confirmed=self.checker.confirmed,
            records=[dict(row,cells=packed(row['cells'])) for row in self.checker.records],
            state_encoding='1024 two-bit cells; cell=bank*256+set*4+way; cell0 at bits1:0',
            failure=None if self.checker.failure is None and exc is None else repr(self.checker.failure or exc),
            trace_kind='abtb-counter-state')
        if exc_type is None:
            report['summary']=self.checker.summary()
        dump_trace((self.output/f'counter-bank{self.bank}.json'), report)
        write_functional_coverage(CoverageDatabase([self.coverage,self.gates]), output_path(self.output/f'functional-coverage-counter-bank{self.bank}.json'))

    def validate(self,prediction,*,pc,set_index,phase):
        check=self.checker.check
        check((1,1<<self.bank,set_index),
              (prediction.meta['valid'],prediction.meta['bankMask'],prediction.meta['setIdx']),
              phase=phase+'.meta-route',pc=pc)
        residents=self.known.get(set_index,{})
        counters=self.checker.reference.cells
        profile=[]
        for way,actual in enumerate(prediction.entries):
            vector=residents.get(way)
            wanted=int(vector is not None)
            check(wanted,actual.valid,phase=phase+'.entry-valid',way=way,pc=pc)
            micro=prediction.micro_tage['result'][way]
            check(wanted,micro['valid'],phase=phase+'.micro-valid',way=way,pc=pc)
            check(wanted,prediction.meta['entries'][way]['hit'],phase=phase+'.meta-hit',way=way,pc=pc)
            if vector is None:
                continue
            value=counters[index(self.bank,set_index,way)]
            expected=dict(valid=1,taken=int(value>=2),target=vector.target,position=vector.position,
                branch_type=1,ras_action=0)
            check(expected,asdict(actual),phase=phase+'.full-entry',way=way,pc=pc,counter=value)
            check(dict(taken=int(value>=2),cfiPosition=vector.position,
                    attribute=dict(branchType=1,rasAction=0),isStrongBias=int(value in (0,3))),
                  micro['bits'],phase=phase+'.public-strength',way=way,pc=pc,counter=value)
            check((vector.position,dict(branchType=1,rasAction=0),vector.target&((1<<22)-1)),
                  (prediction.meta['entries'][way]['position'],prediction.meta['entries'][way]['attribute'],
                   prediction.meta['entries'][way]['targetLowerBits']),
                  phase=phase+'.metadata-identity',way=way,pc=pc)
            profile.append(dict(way=way,position=vector.position,target=vector.target,
                                counter=value,taken=int(value>=2),strong=int(value in (0,3))))
        self.profiles.append(dict(phase=phase,pc=pc,bank=self.bank,set_index=set_index,
                                 checked_tick=self.checker.last_tick,entries=profile,actual=asdict(prediction)))
        self.remember_metadata(prediction,pc=pc)
        return prediction

    def remember_metadata(self,prediction,*,pc):
        self.metadata_ticks[id(prediction)]=self.checker.last_tick
        self.metadata_sources.append(dict(tick=self.checker.last_tick,pc=pc,meta=deepcopy(prediction.meta)))

    async def predict(self,*,pc,set_index,phase):
        result=await self.agent.predict(pc,path_hash=self.bank)
        return self.validate(result,pc=pc,set_index=set_index,phase=phase)

    async def train(self,vector,prediction,*,taken,write=None,phase):
        tx=AbtbTraining(pc=vector.pc,target=vector.target,taken=taken,position=vector.position,
                        branch_type=vector.branch_type,meta=deepcopy(prediction.meta))
        self.checker.plan(tx,write=write)
        self.intents.append(dict(after_tick=self.checker.last_tick,phase=phase,
                                 request=asdict(tx),expected_write=write,
                                 metadata_tick=self.metadata_ticks[id(prediction)]))
        await self.agent.train(tx)
        self.checker.raise_failure()

    async def qualify_gates(self,vectors,full,*,set_index):
        before=self.checker.reference.cells[:]
        await self.agent.set_enabled(False)
        for taken in (0,1):
            await self.train(vectors[0],full,taken=taken,phase=f'disabled-{taken}')
            self.checker.check(before,self.checker.reference.cells,phase='disabled-ref-holds')
        disabled=await self.agent.predict(vectors[0].pc,path_hash=self.bank)
        self.checker.check((0,(0,0,0,0)),
            (disabled.meta['valid'],tuple(entry.valid for entry in disabled.entries)),
            phase='real-disabled-metadata')
        self.remember_metadata(disabled,pc=vectors[0].pc)
        await self.agent.set_enabled(True)
        await self.predict(pc=vectors[0].pc,set_index=set_index,phase='reenabled-unchanged')
        for taken in (0,1):
            await self.train(vectors[0],disabled,taken=taken,phase=f'invalid-meta-{taken}')
            await self.predict(pc=vectors[0].pc,set_index=set_index,phase=f'invalid-meta-holds-{taken}')
        for role in ('disabled_nt','disabled_t','invalid_meta_nt','invalid_meta_t'):
            self.gates.sample(dict(bank=self.bank,set_index=set_index,role=role))

    async def case(self,set_index):
        vectors=tuple(replace(vector,target=0x40080000+self.bank*0x10000+set_index*0x100+i*0x20)
            for i,vector in enumerate(same_pc_position_vectors(self.bank,set_index,count=4)))
        self.known[set_index]={}
        for vector in reversed(vectors):
            prediction=await self.predict(pc=vector.pc,set_index=set_index,phase='populate-before')
            way=victim(self.checker.reference.plru[self.bank][set_index])
            write=dict(bank=self.bank,set_index=set_index,way=way,reset_counter=1)
            await self.train(vector,prediction,taken=1,write=write,phase='independent-cold-allocation')
            self.known[set_index][way]=vector
            await self.predict(pc=vector.pc,set_index=set_index,phase='populate-after')
        self.checker.check(set(range(4)),set(self.known[set_index]),phase='all-physical-ways-populated')
        full=await self.predict(pc=vectors[0].pc,set_index=set_index,phase='initial-full')
        await self.qualify_gates(vectors,full,set_index=set_index)
        for beat in range(3):
            full=await self.predict(pc=vectors[0].pc,set_index=set_index,phase=f'negative-before-{beat}')
            await self.train(vectors[0],full,taken=0,phase=f'negative-step-{beat}')
            await self.predict(pc=vectors[0].pc,set_index=set_index,phase=f'negative-after-{beat}')
        for vector in vectors:
            for beat in range(4):
                full=await self.predict(pc=vector.pc,set_index=set_index,phase=f'positive-before-{vector.position}-{beat}')
                await self.train(vector,full,taken=1,phase=f'positive-step-{vector.position}-{beat}')
                await self.predict(pc=vector.pc,set_index=set_index,phase=f'positive-after-{vector.position}-{beat}')
            full=await self.predict(pc=vector.pc,set_index=set_index,phase=f'strong-negative-before-{vector.position}')
            await self.train(vector,full,taken=0,phase=f'strong-negative-step-{vector.position}')
            await self.predict(pc=vector.pc,set_index=set_index,phase=f'strong-negative-after-{vector.position}')
        observed={(item['way'],item['transition']) for item in self.checker.confirmed
                  if item['bank']==self.bank and item['set_index']==set_index}
        self.checker.check({(way,t) for way in range(4) for t in TRANSITIONS},
            {(way,t) for way,t in observed if t in TRANSITIONS},phase='every-cell-all-eight-transitions',set_index=set_index)
        self.completed_sets.append(set_index)

    async def scrub(self):
        contexts=[(next(iter(ways.values())).pc,s) for s,ways in sorted(self.known.items())]
        for offset in range(0,len(contexts),16):
            batch=contexts[offset:offset+16]
            transfers=[self.agent.submit_predict(pc,path_hash=self.bank) for pc,_ in batch]
            await self.agent.drain_predictions()
            ticks=[transfer.accepted_event.tick for transfer in transfers]
            self.checker.check(list(range(ticks[0],ticks[0]+2*len(ticks),2)),ticks,phase='pipelined-read-acceptance')
            for (pc,s),transfer in zip(batch,transfers,strict=True):
                actual=await transfer
                self.checker.check(transfer.accepted_event.tick+4,transfer.completed_event.tick,
                                   phase='pipelined-read-response-latency')
                self.validate(actual,pc=pc,set_index=s,phase='full-retained-neighbor-revisit')
