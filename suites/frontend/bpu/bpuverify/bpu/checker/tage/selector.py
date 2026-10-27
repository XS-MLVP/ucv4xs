"""Sixteen selector registers from reset; input/source/T2/T3/commit association."""
from collections import deque,Counter
from copy import deepcopy
from dataclasses import asdict
from toffee import CheckContext,Scoreboard,ScoreboardMode
from bpuverify.bpu.model.tage.selector import INITIAL,COUNT,feedback_votes,update_selectors,read_projection
from bpuverify.bpu.model.sc.model import encoded_payload,canonical
from bpuverify.bpu.model.sc.metadata import tage_meta_for_position,mbtb_meta_for_position


class TageSelectorChecker:
    def __init__(self,coverage=None,*,routing=None):
        self.coverage=coverage;self.routing=routing
        self.board=Scoreboard('bpu.tage.selector')
        self.values=(INITIAL,)*COUNT
        self.initialized=False;self.failure=None;self.last_tick=None
        self.phase='setup';self.plans=deque()
        self.case=dict(scope='zero-history fresh-source integrated TAGE selector')
        self.pending={};self.reads={};self.effect=None
        self.records=deque(maxlen=64);self.events=deque(maxlen=32)
        self.counts=Counter()

    def check(self,expected,actual,field,**details):
        self.board.check(expected=expected,actual=actual,context=CheckContext(
            self.board.name,ScoreboardMode.DIRECT,sequence_id=self.last_tick,
            request=dict(field=field,phase=self.phase,**details)))

    def plan(self,tx,source):
        self.raise_failure()
        self.check(source.meta.resolve,tx.resolve_meta,'unmodified_genuine_prediction_metadata')
        self.plans.append(dict(bits=encoded_payload(canonical(asdict(tx))),
            prediction_tick=source.prediction_tick,meta_tick=source.meta_tick))

    def raise_failure(self):
        if self.failure is not None:raise self.failure

    def capture(self,observation):
        if self.failure is None:
            try:self.observe(observation.value,observation.event.tick)
            except Exception as error:
                self.failure=error
                if self.effect is not None:
                    self.events.append(dict(self.effect,status='failed',failure=repr(error)))

    def observe(self,row,tick):
        row=canonical(row)
        if self.last_tick is not None:self.check(self.last_tick+2,tick,'lossless_selector_observation')
        self.last_tick=tick;self.counts['frames']+=1
        self.records.append(dict(tick=tick,selectors=row['selectors'],fire=row['fire'],
            expected_selectors=self.values,prediction=deepcopy(row.get('prediction'))))
        if not self.initialized:
            self.check(1,row['reset'],'initialize_selectors_from_hardware_reset')
            self.initialized=True
        else:
            self.check(list(self.values),list(row['selectors']),'all_sixteen_reset_derived_selectors')
            if self.effect is not None:
                self.check(self.effect['committed_tick'],tick,'exact_selector_commit_source')
                for event in self.effect['events']:
                    if self.coverage is not None:
                        self.coverage.sample('update','checked',event,accepted_tick=self.effect['accepted_tick'],committed_tick=tick)
                if self.routing is not None:
                    for vote in self.effect['routes']:
                        self.routing.sample('checked',vote,accepted_tick=self.effect['accepted_tick'],
                            prediction_tick=self.effect['prediction_tick'],meta_tick=self.effect['meta_tick'],committed_tick=tick)
                self.counts['checked_updates']+=1
                self.events.append(dict(self.effect,status='checked'))
                self.effect=None
        if row['reset']:
            self.values=(INITIAL,)*COUNT;self.pending.clear();self.reads.clear();return
        train=row['training'];accepted=bool(train['valid'] and train['ready'])
        conditional=any(branch['valid'] and branch['bits']['attribute']['branchType']==1 for branch in train['bits']['branches'])
        admitted=int(accepted and conditional and row['enable'])
        self.check(admitted,row['fire'][0],'actual_TAGE_enable_conditional_accept_gate')
        self.check(admitted,row['fire'][1],'observed_T1_from_this_accepting_edge')
        if admitted:
            source=dict(accepted_tick=tick,bits=deepcopy(train['bits']),phase=self.phase)
            if self.phase!='setup':
                self.check(True,bool(self.plans),'every_exercise_accept_planned')
                planned=self.plans.popleft();self.check(planned['bits'],train['bits'],'complete_actual_public_feedback_payload')
                source.update(prediction_tick=planned['prediction_tick'],meta_tick=planned['meta_tick'])
            source['votes'],source['need_read']=feedback_votes(train['bits'])
            self.pending[tick+4]=source;self.reads[tick+2]=source
            self.counts['accepted']+=1
        read=self.reads.pop(tick,None)
        self.check(int(read is not None),row['fire'][2],'T2_from_exact_actual_T0_source')
        if read is not None:
            self.check(1-read['need_read'],row['use_meta'],'actual_T2_metadata_or_SRAM_mode')
            if read['need_read']:
                pc=read['bits']['start_pcs'][0][0]['addr']
                self.check([(pc>>11)&8191]*8,list(row['raw_tags']),'zero_PHR_raw_tags_from_actual_source_PC')
                for vote in read['votes']:
                    if vote['valid']:
                        projection=read_projection(row['reads'],row['raw_tags'],vote)
                        self.check({key:vote['meta'][key] for key in projection},projection,
                            'fresh_prediction_matches_actual_training_read_operands',accepted_tick=read['accepted_tick'],slot=vote['slot'])
        source=self.pending.pop(tick,None)
        if source is not None:
            before=self.values;after,events=update_selectors(self.values,source['votes'])
            if source['phase']!='setup':
                self.effect=dict(accepted_tick=source['accepted_tick'],committed_tick=tick+2,
                    prediction_tick=source['prediction_tick'],meta_tick=source['meta_tick'],
                    before=before,after=after,events=events,
                    routes=[deepcopy(vote) for vote in source['votes'] if vote['valid'] and (vote['inc'] or vote['dec'])])
                for event in events:
                    if self.coverage is not None:
                        self.coverage.sample('update','reached',event,accepted_tick=source['accepted_tick'],T3_tick=tick)
                if self.routing is not None:
                    for vote in self.effect['routes']:
                        self.routing.sample('reached',vote,accepted_tick=source['accepted_tick'],
                            prediction_tick=source['prediction_tick'],meta_tick=source['meta_tick'],T3_tick=tick)
        self.check(int(source is not None),row['fire'][3],'T3_from_exact_actual_T0_source')
        if source is not None:
            for vote,actual in zip(source['votes'],row['votes'],strict=True):
                self.check(vote['valid'],actual['valid'],'all_sixteen_T3_entry_qualifiers',slot=vote['slot'])
                if vote['valid']:
                    self.check({key:vote[key] for key in ('index','inc','dec')},
                        {key:actual[key] for key in ('index','inc','dec')},'independent_qualified_selector_votes',slot=vote['slot'])
            self.values=after

    def check_public(self,source,position,*,phr,positions,targets):
        self.raise_failure()
        meta=tage_meta_for_position(source,position)
        self.check(1,meta['hasProvider'],'real_provider_present_for_selector_consumer')
        index=2*meta['providerTableIdx']+meta['altConf']
        frames=[row for row in self.records if row['tick']==source.meta_tick-2]
        self.check(1,len(frames),'one_exact_TAGE_S2_consumer_before_associated_S3')
        frame=frames[0];reference=frame['expected_selectors']
        expected=int(not (meta['providerTakenCtr_value'] in (3,4) and reference[index]>=16))
        if meta['providerTakenCtr_value'] in (3,4) and self.coverage is not None:
            event=dict(rule='provider' if expected else 'alternate',index=index,selector=reference[index])
            self.coverage.sample('selection','reached',event,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick)
        self.check(expected,meta['useProvider'],'fresh_public_provider_selection_from_reference_selector',
            prediction_tick=source.prediction_tick,index=index,selector=reference[index])
        observed=frame['prediction']
        self.check((1,source.prediction.start_pc),(observed['fire'],observed['pc']),
            'actual_TAGE_S2_event_matches_public_source')
        directions=[]
        for p in positions:
            slot,_=mbtb_meta_for_position(source,p);entry=tage_meta_for_position(source,p)
            raw=observed['slots'][slot]
            bucket=2*entry['providerTableIdx']+entry['altConf']
            selected=int(not (entry['providerTakenCtr_value'] in (3,4) and reference[bucket]>=16))
            self.check({key:entry[key] for key in raw['meta']},raw['meta'],
                'complete_same_event_public_TAGE_selection_inputs',slot=slot)
            direction=int(entry['providerTakenCtr_value']>=4) if selected else entry['altOrBasePred']
            self.check(int(selected or entry['hasAlt']),raw['valid'],'actual_TAGE_prediction_valid',slot=slot)
            self.check(direction,raw['taken'],'actual_TAGE_prediction_direction',slot=slot)
            directions.append(direction)
        first=next((i for i,direction in enumerate(directions) if direction),None)
        final=[row for row in phr.records if row['tick']==source.meta_tick]
        self.check(1,len(final),'one_exact_associated_final_BPU_S3_consumer')
        row=final[0]
        self.check((source.prediction.start_pc,targets[first] if first is not None else source.prediction.start_pc+16,
            int(first is not None),positions[first] if first is not None else 0),
            (row['parent']['s3_pc'],row['parent']['s3_target'],row['parent']['s3_taken'],
                row['boundary']['s3']['prediction']['position']),
            'complete_associated_BPU_final_prediction_from_selector')
        if meta['providerTakenCtr_value'] in (3,4) and self.coverage is not None:
            self.coverage.sample('selection','checked',event,prediction_tick=source.prediction_tick,meta_tick=source.meta_tick)
        return meta

    def summary(self):
        self.raise_failure()
        self.check((0,0,0,None),(len(self.plans),len(self.pending),len(self.reads),self.effect),'all_selector_sources_and_effects_drained')
        return dict(counts=dict(self.counts),selectors=self.values,checks=asdict(self.board.status),events=list(self.events),
            selector_state_seeded_from_DUT=False,training_SRAM_read_operands_are_explicit_inputs=True,
            independent_full_TAGE_SRAM_reference_claimed=False)
