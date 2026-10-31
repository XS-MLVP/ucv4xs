"""Accepted source -> T1 -> counter; independent clear cursors and SRAM effects."""
from collections import deque,Counter
from copy import deepcopy
from dataclasses import asdict,replace
from toffee import CheckContext,Scoreboard,ScoreboardMode
from suites.frontend.bpu.bpu.model.sc.model import canonical,encoded_payload
from suites.frontend.bpu.bpu.model.ittage_aging import SETS,BANKS,MAX_TICK,USEFUL_MASK,ENTRY_MASK,tick_step,table_step,write_plan
from suites.frontend.bpu.bpu.checker.ittage import check_metadata,check_coherent_target


class IttageAgingChecker:
    def __init__(self,coverage):
        self.coverage,self.board=coverage,Scoreboard('bpu.ittage.aging')
        self.counter,self.pulse,self.t1,self.normal=0,0,None,[None]*len(SETS)
        self.tables=[(0,0) for _ in SETS]
        self.next=None;self.initialized=False;self.failure=None;self.last_tick=None;self.last_phase=None
        self.plans=deque();self.contexts={};self.pending_clears=set();self.seen_clears=set()
        self.counts=Counter();self.records=deque(maxlen=64);self.events=deque(maxlen=32)
        self.phase='setup';self.case=dict(scope='two zero-history PC-region contexts; one global useful lifecycle')

    def check(self,expected,actual,point):
        self.board.check(expected=canonical(expected),actual=canonical(actual),context=CheckContext(
            self.board.name,ScoreboardMode.DIRECT,sequence_id=self.last_tick,
            request=dict(point=point,phase=self.phase,counter=self.counter,tables=self.tables,
                pending_sources=len(self.plans),pending_clear_writes=len(self.pending_clears))))

    def raise_failure(self):
        if self.failure is not None:raise self.failure

    def plan(self,tx,source):
        self.raise_failure();value=canonical(asdict(tx));branch,=value['branches']
        self.check((1,3,1),(int(branch is not None),branch['branch_type'],branch['taken']),'one taken other-indirect source')
        self.check(tx.pc,source.prediction.start_pc,'original prediction PC matches accepted feedback context')
        self.check(source.meta.resolve,tx.resolve_meta,'unmodified genuine metadata')
        self.plans.append(dict(bits=encoded_payload(value),value=value,prediction_tick=source.prediction_tick,
            meta_tick=source.meta_tick,pc=tx.pc))

    def capture(self,phase,observation):
        if self.failure is None:
            try:self.observe(phase,observation)
            except Exception as error:self.failure=error

    def registers(self,row):
        self.check(self.counter,row['counter'],'complete reset-derived global tick')
        self.check(self.tables,[(t['busy'],t['index']) for t in row['tables']],'all three busy/cursor registers')
        self.check([self.pulse]*len(SETS),[t['start'] for t in row['tables']],'one associated reset pulse at all tables')

    def observe(self,phase,observation):
        row,tick=canonical(observation.value),observation.event.tick
        if self.last_tick is not None:
            self.check(self.last_tick+1,tick,'lossless two-phase observation')
            self.check('rising' if self.last_phase=='preedge' else 'preedge',phase,'alternating observations')
        self.last_tick,self.last_phase=tick,phase;self.counts['frames']+=1
        self.records.append(dict(tick=tick,phase=phase,counter=row['counter'],tables=[(t['busy'],t['index']) for t in row['tables']]))
        if not self.initialized:
            self.check(('preedge',1),(phase,row['reset']),'genuine hardware reset required')
            self.initialized=True
        if phase=='rising':
            self.check(True,self.next is not None,'one exact preedge effect')
            effect,self.next=self.next,None
            self.counter,self.pulse,self.tables=effect['counter'],effect['pulse'],effect['tables']
            self.t1,self.normal=effect['t1'],effect['normal']
            self.registers(row)
            for event in effect['training']:
                self.coverage.sample('training','checked',dict(event,committed_tick=tick));self.events.append(dict(event,status='checked'))
            for event in effect['maintenance']:
                self.coverage.sample('maintenance','checked',dict(event,committed_tick=tick))
            # This checker audits physical maintenance. Logical table contents
            # and historical consumers belong to the independent semantic model.
            return
        if row['reset']:
            self.check(0,len(self.plans),'reset cannot discard feedback sources')
            self.next=dict(counter=0,pulse=0,tables=[(0,0) for _ in SETS],t1=None,normal=[None]*len(SETS),training=[],maintenance=[],cleared=[])
            return
        self.registers(row)
        source=self.t1;value=None if source is None else source['value']
        after,rule=tick_step(self.counter,value);start=int(self.counter==MAX_TICK)
        training=[];maintenance=[];cleared=[]
        if rule is not None:
            event=dict(rule=rule,before=self.counter,after=after,T1_tick=tick,
                **({key:source[key] for key in ('pc','prediction_tick','meta_tick','accepted_tick')} if source else {}))
            self.coverage.sample('training','reached',event);training.append(event)
            self.counts[rule]+=1
            if rule=='decrement' and after<self.counter:self.counts['effective_decrements']+=1
        if start:
            self.counts['epochs']+=1
            self.coverage.sample('maintenance','reached',dict(rule='sweep-completed',start_tick=tick))
        self.check(int(source is not None),row['stage']['valid'],'T1 from exact preceding accepted source')
        if source is not None:
            meta=value['resolve_meta']['ittage'];branch,=value['branches'];stage=row['stage']
            self.check(value['pc'],stage['pc'],'T1 source PC')
            self.check(meta['provider']['valid'],stage['provider'],'T1 provider qualifier')
            self.check(meta['allocate']['valid'],stage['allocate'],'T1 allocation qualifier')
            if meta['provider']['valid']:
                self.check((meta['providerCnt_value'],meta['providerTarget_addr']),(stage['counter'],stage['target']),'T1 provider counter/target')
            self.check([1]+[0]*7,[b['valid'] for b in stage['branches']],'complete T1 branch valid mask')
            self.check((branch['target'],1,3,branch['mispredict']),tuple(stage['branches'][0][k] for k in ('target','taken','kind','mispredict')),'T1 indirect payload')
        future=[]
        for table,(busy,index) in enumerate(self.tables):
            actual=row['tables'][table];request=bool(actual['request']['valid'] and actual['request']['ready'])
            normal=self.normal[table]
            self.check(int(normal is not None),actual['update']['valid'],'qualified delayed normal table update')
            if normal is not None:
                for field in normal:
                    if field=='old_counter' and normal['allocate']:continue # allocation ignores this operand
                    if field=='useful' and not normal['useful_valid']:continue # explicitly excluded by the write mask
                    self.check(normal[field],actual['update'][field],f'complete table update {table}.{field}')
            advance=bool(busy and not(request or normal is not None))
            self.check(int(advance),actual['advance'],'read/update priority over useful maintenance')
            future.append(table_step(busy,index,request=request,update=normal is not None,start=bool(self.pulse),sets=SETS[table]))
            for name,condition in (('read-blocked',busy and request),('update-blocked',busy and normal is not None)):
                if condition:
                    event=dict(rule=name,table=table,index=index,tick=tick)
                    self.coverage.sample('maintenance','reached',event);maintenance.append(event);self.counts[name]+=1
            for bank,ports in enumerate(actual['banks']):
                if advance:
                    self.check((1,index,USEFUL_MASK,0),tuple(ports['enqueue'][k] for k in ('valid','index','mask','useful')),'full useful-only clear enqueue')
                    key=table,bank,index;self.check(False,key in self.pending_clears or key in self.seen_clears,'one clear per table/bank/set')
                    self.pending_clears.add(key)
                else:
                    active=bool(normal is not None and bank==normal['pc']&1)
                    self.check(int(active),ports['enqueue']['valid'],'normal update bank qualification; no stray maintenance enqueue')
                    if active:
                        mask=ENTRY_MASK if normal['useful_valid'] else ENTRY_MASK^USEFUL_MASK
                        self.check(((normal['pc']>>1)&(SETS[table]-1),mask),
                            (ports['enqueue']['index'],ports['enqueue']['mask']),'complete normal zero-PHR address and write mask')
                        if normal['useful_valid']:self.check(normal['useful'],ports['enqueue']['useful'],'effective normal useful payload')
                ram=ports['ram']
                if ram['valid'] and ram['ready'] and ram['mask']==USEFUL_MASK:
                    key=table,bank,ram['index']
                    self.check(True,key in self.pending_clears,'SRAM useful write from planned maintenance')
                    self.check(0,ram['useful'],'actual SRAM useful cleared')
                    self.pending_clears.remove(key);self.seen_clears.add(key);cleared.append(key)
                    self.counts['clear_write_accepts']+=1
        admitted=bool(row['feedback_valid'] and row['feedback_ready'] and row['enable'])
        next_source=None
        if admitted:
            self.check(True,bool(self.plans),'every accepting public source planned')
            next_source=self.plans.popleft()
            self.check(next_source['bits'],row['feedback'],'complete accepted actual public feedback')
            next_source['accepted_tick']=tick;self.counts['accepted']+=1
        self.next=dict(counter=after,pulse=start,tables=future,t1=next_source,normal=write_plan(value),
            training=training,maintenance=maintenance,cleared=cleared)

    def finish_maintenance(self):
        self.raise_failure()
        expected={(t,b,i) for t,n in enumerate(SETS) for b in range(BANKS) for i in range(n)}
        self.check((1,0,0,[0]*len(SETS)),(self.counts['epochs'],len(self.pending_clears),len(expected-self.seen_clears),[s[0] for s in self.tables]),'all table SRAM sweeps completed and drained')
        self.check(expected,self.seen_clears,'exact full maintenance write footprint')
        self.coverage.sample('maintenance','checked',dict(rule='sweep-completed',committed_tick=self.last_tick,writes=len(expected)))

    def public(self,source,pc,model,phr,*,feedback_target,position,after_clear=False,had_useful=False):
        self.raise_failure()
        event=dict(rule='cleared-useful' if had_useful else 'retained-zero-useful',pc=pc,
            prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,expected=model.metadata())
        if after_clear:self.coverage.sample('consumption','reached',event)
        self.check(pc,source.prediction.start_pc,'complete public prediction source PC')
        check_metadata(self.board,model,source,phase=self.phase)
        check_coherent_target(self.board,phr,source,model.target(),feedback_target,position,
            CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=source.meta_tick,request=event))
        if after_clear:self.coverage.sample('consumption','checked',event)

    def summary(self):
        self.raise_failure()
        self.check((0,None,[None]*len(SETS)),(len(self.plans),self.t1,self.normal),'all feedback pipeline effects drained')
        status=self.board.status
        return dict(counts=dict(self.counts),counter=self.counter,tables=self.tables,
            checks=asdict(replace(status,first_failure=None)),events=list(self.events),
            state_seeded_from_DUT=False,full_ITTAGE_SRAM_or_FTQ_reference_claimed=False)
