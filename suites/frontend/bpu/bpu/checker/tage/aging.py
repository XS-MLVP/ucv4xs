"""Reset-derived candidate set and global lifecycle; no observed state seeding."""
from collections import deque,Counter
from copy import deepcopy
from dataclasses import asdict
from toffee import CheckContext,Scoreboard,ScoreboardMode
from suites.frontend.bpu.bpu.model.tage.aging import empty_set,prediction,transition,counter_transition,clear_step,SETS
from suites.frontend.bpu.bpu.checker.tage.selector import TageSelectorChecker
from suites.frontend.bpu.bpu.coverage.tage.selector import SelectorRoutingCoverage
from suites.frontend.bpu.bpu.model.sc.metadata import mbtb_meta_for_position,tage_meta_for_position
from suites.frontend.bpu.bpu.model.sc.model import encoded_payload,canonical
from suites.frontend.bpu.bpu.model.abtb.final_not_taken import fall_through


class TageAgingChecker:
    def __init__(self,coverage,trigger):
        self.coverage=coverage;self.routing=SelectorRoutingCoverage();self.selector=TageSelectorChecker(routing=self.routing)
        self.board=Scoreboard('bpu.tage.useful_aging');self.case=dict(trigger=trigger)
        self.phase='setup';self.failure=None;self.last_tick=None;self.initialized=False
        self.cells=empty_set();self.counter=0;self.busy=0;self.banks=[(0,0)]*32
        self.plans=deque();self.pending={};self.reads={};self.effect=None;self.override=None;self.allocation_effect=None
        self.records=deque(maxlen=64);self.events=deque(maxlen=32);self.counts=Counter()
        self.clear_addresses=[set() for _ in range(64)];self.epochs=0;self.restored_tag=None

    def check(self,expected,actual,field,**context):
        self.board.check(expected=canonical(expected),actual=canonical(actual),context=CheckContext(
            self.board.name,ScoreboardMode.DIRECT,sequence_id=self.last_tick,
            request=dict(field=field,phase=self.phase,**context)))

    def raise_failure(self):
        if self.failure is not None:raise self.failure
        self.selector.raise_failure()

    def plan(self,tx,source,*,enabled):
        self.check(source.meta.resolve,tx.resolve_meta,'unmodified_actual_metadata')
        if enabled:
            self.selector.phase='aging.'+self.phase
            self.selector.plan(tx,source)
        self.plans.append(dict(bits=encoded_payload(canonical(asdict(tx))),enabled=enabled,
            prediction_tick=source.prediction_tick,meta_tick=source.meta_tick))

    def capture(self,observation):
        if self.failure is not None:return
        try:self.observe(observation.value,observation.event.tick)
        except Exception as error:
            self.failure=error
            self.events.append(dict(tick=observation.event.tick,status='failed',failure=repr(error)))

    def sample(self,family,status,rule,**context):
        self.coverage.sample(family,status,rule,tick=self.last_tick,**context)

    def observe(self,row,tick):
        row=canonical(row);s,a=row['selector'],row['age']
        self.last_tick=tick;self.counts['frames']+=1
        self.records.append(dict(tick=tick,age=deepcopy(a),expected_cells=deepcopy(self.cells)))
        if not self.initialized:self.check(1,s['reset'],'genuine_reset_initialization');self.initialized=True
        self.check(self.counter,a['counter'],'independent_global_failure_counter')
        self.check(self.busy,a['busy'],'global_clear_lifecycle')
        actual_banks=[(b['busy'],b['index']) for t in a['tables'] for b in t['banks']]
        self.check(self.banks,actual_banks,'all_thirty_two_bank_clearing_states')
        if s['reset']:
            self.selector.observe(s,tick)
            self.cells=empty_set();self.counter=0;self.busy=0;self.banks=[(0,0)]*32;return
        if self.effect is not None:
            self.check(self.effect['tick'],tick,'next_actual_counter_commit')
            if self.effect['rule']=='allocation-restored':
                self.check(None,self.allocation_effect,'one_pending_recovered_allocation')
                self.allocation_effect=self.effect
            else:
                self.sample('training','checked',self.effect['rule'],source=self.effect['source'])
                self.events.append(dict(self.effect,status='checked'))
            self.effect=None
        accepted=bool(s['training']['valid'] and s['training']['ready'])
        if accepted:
            self.check(True,bool(self.plans),'every_feedback_owned_by_driver_plan')
            source=self.plans.popleft();self.check(source['bits'],s['training']['bits'],'complete_actual_feedback')
            self.check(int(source['enabled']),s['enable'],'CSR_qualification_from_intended_driver_control')
            self.counts['accepted']+=1
            if source['enabled']:
                source['accepted_tick']=tick;self.pending[tick+4]=source;self.reads[tick+2]=source
        source=self.reads.pop(tick,None)
        if source is not None:
            pc=source['bits']['start_pcs'][0][0]['addr']
            self.check((1,[2]*8,[((pc>>11)&8191)]*8),(a['bank'],a['sets'],s['raw_tags']),'one_known_candidate_set_and_independent_tags')
            if not s['use_meta']:
                self.check(self.cells,s['reads'],'all_sixteen_valid_training_read_operands_from_expected_writes')
        source=self.pending.pop(tick,None);result=None
        if source is not None:
            bits=source['bits'];branch=bits['branches'][0]['bits'];pc=bits['start_pcs'][0][0]['addr']
            owners=[entry for bank in bits['meta']['mbtb_entries'] for entry in bank]
            matches=[i for i,o in enumerate(owners) if o['rawHit'] and o['position']==branch['cfiPosition']]
            self.check(1,len(matches),'one_genuine_MainBTB_owner')
            owner=matches[0];meta=bits['meta']['tage_entries'][owner]
            result=transition(self.cells,meta,pc=pc,position=branch['cfiPosition'],taken=branch['taken'],
                mispredict=branch['mispredict'],random_mask=a['random'])
        after,start=counter_transition(self.counter,fire=int(source is not None),
            need=result['need'] if result else 0,can=result['can'] if result else 0,busy=self.busy)
        rule=None
        if start:rule='reset-start-demand' if result['need'] else 'reset-start-correct-update'
        elif result and result['need'] and not result['can'] and not self.busy:
            rule='failed-saturates' if after==255 else 'failed-increment';self.counts['increments']+=1
        elif result and result['allocate'] and self.epochs:
            rule='allocation-restored';self.restored_tag=((pc>>11)&8191)^branch['cfiPosition']
        if rule:
            self.sample('training','reached',rule,source=source)
            self.effect=dict(tick=tick+2,rule=rule,source=source)
        # Reachability is owned by the accepted source, not by assertion-call order.
        self.selector.observe(s,tick)
        self.check(start,a['start'],'saturated_real_T3_triggers_once_even_without_allocation_demand')
        if result:
            # Without allocation demand the allocator Mux1H has no selected branch;
            # its candidates may refer to an old, unused SRAM response in meta mode.
            keys=('need','allocate','can','table','way') if result['need'] else ('need','allocate')
            self.check({k:result[k] for k in keys},{k:a[k] for k in keys},
                'independent_qualification_and_valid_random_filter_input')
            for t,(wanted,table) in enumerate(zip(result['writes'],a['tables'],strict=True)):
                write=table['write'];mask=sum(int(w is not None)<<i for i,w in enumerate(wanted))
                self.check(int(bool(mask)),write['valid'],'actual_qualified_table_write',table=t)
                if mask:
                    self.check((2,1,mask),(write['index'],write['bank'],write['way']),'complete_write_object',table=t)
                    for w,entry in enumerate(wanted):
                        if entry is None:continue
                        actual=write['entries'][w]
                        self.check((entry['entry_en'],entry['useful_en'],entry['taken']),
                            (actual['entry_en'],actual['useful_en'],actual['taken']),'independent_write_enables',table=t,way=w)
                        if entry['entry_en']:
                            self.check({k:entry['entry'][k] for k in ('valid','tag','counter')},
                                {k:actual[k] for k in ('valid','tag','counter')},'independent_written_entry',table=t,way=w)
                        if entry['useful_en']:
                            self.check(entry['entry']['useful'],actual['useful'],'independent_useful_write',table=t,way=w)
                            if start:self.override=dict(tick=tick+2,table=t,way=w,source=source)
            self.cells=result['after'];self.counts['T3']+=1;self.counts['allocations']+=result['allocate']
        if start:
            self.epochs+=1;self.clear_addresses=[set() for _ in range(64)]
            for table in self.cells:
                for entry in table:entry['useful']=0
        if self.override is not None and self.override['tick']==tick:
            o=self.override;table=a['tables'][o['table']]
            self.sample('maintenance','reached','clear-overrides-normal-useful-update',source=o['source'])
            self.check((1,1,1,0),(table['staged_valid'],table['staged_useful'][o['way']],
                table['banks'][0]['busy'],table['banks'][0]['ports'][o['way']]['enq']),
                'actual_staged_useful_update_is_suppressed_during_clear')
            self.sample('maintenance','checked','clear-overrides-normal-useful-update',source=o['source']);self.override=None
        ready=[]
        self.check([start]*64,[p['flush'] for table in a['tables'] for bank in table['banks'] for p in bank['ports']],
            'all_useful_queues_receive_the_exact_common_flush_start')
        for t,table in enumerate(a['tables']):
            self.check(int(any(b for b,_ in self.banks[t*4:t*4+4])),table['busy'],'table_busy_OR')
            self.check(start,table['start'],'same_clear_start_for_each_table')
            for b,bank in enumerate(table['banks']):
                active,index=self.banks[t*4+b];ready.append(bank['ports'][0]['ready'])
                if start or active:
                    for w,port in enumerate(bank['ports']):
                        self.check((1,index,0,0),(port['valid'],port['address'],port['data'],port['enq']),
                            'clear_priority_request_and_no_normal_useful_enqueue',table=t,bank=b,way=w)
                        if port['ready']:self.clear_addresses[(t*4+b)*2+w].add(index);self.counts['clear_write_accepts']+=1
        old_busy=self.busy;self.busy=int(bool(start or (self.busy and any(b for b,_ in self.banks))))
        self.banks=clear_step(self.banks,start=start,ready=ready);self.counter=after
        if old_busy and not self.busy:
            self.sample('maintenance','reached','all-banks-complete')
            self.check([set(range(SETS))]*64,self.clear_addresses,'all_rows_cleared_by_actual_write_handshakes')
            # The global register takes one more edge to reflect this independently derived completion.
            self.completed_tick=tick+2
        if getattr(self,'completed_tick',None)==tick:
            self.sample('maintenance','checked','all-banks-complete');self.counts['clear_completed']+=1;self.completed_tick=None

    def public(self,source,pc,position,target,phr):
        self.raise_failure();slot,owner=mbtb_meta_for_position(source,position)
        frames=[r for r in self.selector.records if r['tick']==source.meta_tick-2]
        self.check(1,len(frames),'one_exact_S2_for_this_public_source')
        reference=frames[0]['expected_selectors']
        expected=prediction(self.cells,pc,position,owner['counter_value'],reference)
        tag=((pc>>11)&8191)^position;rule=None
        if self.epochs and expected['hasProvider']:
            rule='new-provider' if tag==self.restored_tag else 'retained-provider'
            self.sample('consumer','reached',rule,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick)
        self.check(expected,tage_meta_for_position(source,position),'complete_public_metadata_from_known_candidate_state')
        raw=frames[0]['prediction'];self.check((1,pc),(raw['fire'],raw['pc']),'exact_actual_TAGE_source')
        taken=int(expected['providerTakenCtr_value']>=4) if expected['useProvider'] else expected['altOrBasePred']
        actual=raw['slots'][slot]
        self.check({key:expected[key] for key in actual['meta']},actual['meta'],'same_event_actual_TAGE_metadata')
        tage_valid=int(expected['useProvider'] or expected['hasAlt'])
        self.check(tage_valid,actual['valid'],'actual_TAGE_prediction_qualification')
        # ParallelPriorityMux has no semantic selected alternate when hasAlt=0.
        # Only valid data is a TAGE prediction; final MainBTB fallback remains checked.
        if tage_valid:self.check(taken,actual['taken'],'actual_valid_TAGE_prediction_direction')
        final=[r for r in phr.records if r['tick']==source.meta_tick]
        self.check(1,len(final),'exact_final_S3_source');f=final[0]
        fall=fall_through(pc)
        self.check((pc,target if taken else fall['target'],taken,position if taken else fall['position']),
            (f['parent']['s3_pc'],f['parent']['s3_target'],f['parent']['s3_taken'],f['boundary']['s3']['prediction']['position']),
            'final_S3_target_direction_and_position')
        if rule:self.sample('consumer','checked',rule,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick)
        if rule=='new-provider' and self.allocation_effect is not None:
            self.check(True,source.prediction_tick>self.allocation_effect['tick'],'actual_new_consumer_after_allocated_effect')
            self.sample('training','checked','allocation-restored',source=self.allocation_effect['source'],
                prediction_tick=source.prediction_tick,meta_tick=source.meta_tick)
            self.events.append(dict(self.allocation_effect,status='checked',consumer_tick=source.meta_tick))
            self.allocation_effect=None
        return expected,taken

    def direction(self,source,phr):
        rows=[r for r in phr.records if r['tick']==source.meta_tick]
        self.check(1,len(rows),'one_actual_final_direction_source')
        self.check(source.prediction.start_pc,rows[0]['parent']['s3_pc'],'final_direction_PC_association')
        return rows[0]['parent']['s3_taken']

    def summary(self):
        self.raise_failure()
        self.check((0,0,0,None,None,None,0),(len(self.plans),len(self.pending),len(self.reads),self.effect,
            self.override,self.allocation_effect,self.busy),'all_sources_effects_and_maintenance_drained')
        return dict(counts=dict(self.counts),counter=self.counter,epochs=self.epochs,cells=self.cells,
            selector=self.selector.summary(),
            checks=asdict(self.board.status),recent_events=list(self.events),observed_state_seeded_reference=False,
            random_filter_is_explicit_input=True,full_MainBTB_or_all_TAGE_SRAM_reference_claimed=False)
