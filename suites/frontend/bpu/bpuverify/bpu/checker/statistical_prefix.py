"""Actual acceptance and exact source preservation around an SC prefix program."""
from collections import Counter
from copy import deepcopy

from toffee import CheckContext, ScoreboardMode

from bpuverify.bpu.model.conditional_prefix import target_state
from bpuverify.bpu.model.statistical_prefix import Layout


class Checks:
    program_type=Layout

    def __init__(self, profile, coverage):
        self.program, self.coverage = self.program_type(profile), coverage
        self.pipeline = None
        self.redirect_count, self.last_redirect = 0, None
        self.feedbacks, self.saved = [], {}
        self.updates = self.cycles = self.guard_cycles = 0
        self.early_sources = Counter()
        self.guard = None

    @property
    def bank(self):
        return self.pipeline.model.sources

    def check(self, expected, actual, point):
        self.pipeline.raise_failure()
        self.pipeline.board.check(expected=expected, actual=actual,
            context=CheckContext(self.pipeline.board.name, ScoreboardMode.DIRECT,
                sequence_id=self.pipeline.last_tick, request=dict(point=point, profile=self.program.profile)))

    def candidates(self, row, events, cycle, model, phase, previous):
        self.events, self.cycle, self.observed = events, cycle, row['observed']
        return ()

    def reached(self, tick, *args):
        pass

    def checked(self, tick, *args):
        events, cycle = self.events, self.cycle
        self.cycles += 1
        self.updates += sum(bool(row['valid'] and any(row['mask'])) for row in self.observed['statistical']['updates'])
        if cycle.fires[1] and not cycle.flushes[0]:
            self.early_sources[cycle.decisions[0].source] += 1
        if events.redirect is not None:
            self.redirect_count += 1
            self.last_redirect = tick, events.redirect.source, events.prediction_ready
        if events.feedback is not None:
            self.feedbacks.append((tick, events.feedback))
        if self.guard is not None:
            self.check(self.guard, target_state(self.bank), 'unexecuted indirect has no semantic learning')

    def snapshots(self, token):
        b = self.bank
        return (b.snapshot(token), b.short_snapshot(token), b.tage_snapshot(token),
            b.tage_snapshot(token, resolved=True), b.target_snapshot(token), b.target_snapshot(token, resolved=True),
            b.statistical_snapshot(token), b.statistical_snapshot(token, resolved=True), b.queries.snapshot(token))

    def save(self, receipt):
        token = self.pipeline.source_token(receipt)
        self.saved.setdefault(token.sequence, (receipt, token, self.snapshots(token), deepcopy(receipt.meta)))
        return token

    def mark(self, rule):
        self.coverage.record(rule, self.pipeline.last_tick)

    def actual(self, event, row):
        if self.guard is None or row['reset']:
            return
        self.check(False, bool(row['region_write'] or any(row['updates']) or any(row['incoming'])
            or any(row['maintenance']) or any(row['write_valid'])), 'actual unexecuted indirect has no update or service')
        expected = tuple(dict(valid=int(region is not None), region=region or 0)
            for region in self.bank.indirect.regions.regions)
        self.check(expected, tuple(row['regions']), 'actual region directory remains independently owned')
        self.guard_cycles += 1

    def numeric_consumer(self,source):
        token=self.save(source)
        compared=self.pipeline.sc_numeric_checked.get(token.history.sequence,{})
        self.check({'read','consume','composition'},set(compared),'fresh consumer has full numeric read, consumed-evidence and composition proof')
        self.check(True,compared['read']<compared['consume'],'independent request response precedes its consumed evidence')
        self.check(compared['consume'],compared['composition'],'numeric composition belongs to the same original consumption boundary')
        original=self.bank.statistical_snapshot(token).read
        families=tuple(family for family in FAMILIES
            if original.context.common_valid or family not in ('global','backward'))
        return dict(owner=token.sequence,read_tick=compared['read'],consumed_tick=compared['consume'],
            all_defined_read_weights_compared=True,all_consumed_family_values_compared=True,
            composition_tick=compared['composition'],all_composed_signed_values_compared=True,
            read_families=families,consumed_families=FAMILIES,
            read_word_count=32 if original.context.common_valid else 24,consumed_word_count=32)

    def finish(self, fresh):
        self.pipeline.raise_failure()
        for receipt, token, snapshots, metadata in self.saved.values():
            self.check(token, self.pipeline.source_token(receipt), 'every saved public receipt retains its original')
            self.check(snapshots, self.snapshots(token), 'all nine original evidence domains are immutable')
            self.check(metadata, receipt.meta, 'public metadata never rewritten by later learning')
        self.mark('all-original-evidence-preserved')
        result=dict(profile=self.program.profile, cycles=self.cycles,
            numeric_consumers=[self.numeric_consumer(fresh)],
            numeric_prediction_checks={key:value for key,value in self.pipeline.counts.items() if key.startswith(('sc-numeric-','sc-composition-'))},
            actual_feedbacks=len(self.feedbacks), signed_masked_weight_updates=self.updates,
            actual_indirect_guard_cycles=self.guard_cycles, early_sources=dict(self.early_sources),
            original_sources=len(self.saved), fresh_owner=self.save(fresh).sequence,
            all_original_domains_immutable=True, independently_composed_algorithms=7,
            complete_FTQ=False, autonomous_early_SC_teaching_proven=False)
        self.coverage.finish()
        return result


# Reuse accepted-read identity checks already exercised by concurrent cases.
from bpuverify.bpu.model.statistical_prefix import ContextLayout
from bpuverify.sc.model.semantic import Context,coordinates,feedback_needs_read,FAMILIES


class ContextChecks(Checks):
    def __init__(self,profile,coverage,*,layout_type=ContextLayout):
        from bpuverify.bpu.checker.statistical import InvalidHistoryEvidence
        super().__init__('conditional-entry.condition-taken',coverage)
        self.program=layout_type(profile)
        self.probe=None
        self.context_reads=[]
        self.context_offers=[]
        self.context_accepts=[]
        self.receipts=[]
        self.originals=()
        self.context_read=None
        self.invalid_history=InvalidHistoryEvidence()
        self.warm_query=None
        self.invalid_history_probe=None

    def open_warm_query(self,receipt):
        import asyncio
        self.check(None,self.warm_query,'one declared cancelled-query probe')
        token=self.save(receipt)
        read=self.bank.statistical_snapshot(token).read
        self.check(True,read.context.common_valid,'warm query starts from real valid condition experience')
        self.warm_query=dict(future=asyncio.get_running_loop().create_future(),
            indices=read.indices[1:3],pc=token.pc,token=None)
        return self.warm_query['future']

    def candidates(self,row,*args):
        super().candidates(row,*args)
        self.expected_patches=self.bank.sc.preview_learning()[0]
        return ()

    def context_source(self,receipt):
        token=self.save(receipt)
        value=self.bank.statistical_snapshot(token,resolved=True)
        source=self.bank.queries.snapshot(token)
        self.check((True,1,int(self.program.backward),0),
            (source.read.valid,source.read.ghr,source.read.bw,source.loop),
            'real executed conditional prefix owns nonzero SC context')
        self.check(source.read,source.metadata,'this uninterrupted valid source has identical read and feedback history')
        self.check(self.bank.queries.sc_history(token),value.original.history,
            'SC read belongs to independently scheduled original history')
        if self.context_read is not None:
            self.check(self.context_read.indices,value.original.read.indices,'new consumer returns to the same five logical features')
        self.mark('real-executed-nonzero-history')
        self.mark('owned-five-family-read')
        return token,value

    def provider(self,receipt):
        token,value=self.context_source(receipt)
        slot,=[i for i,branch in enumerate(value.branches) if branch is not None and branch.position==self.program.position]
        fields=dict(self.bank.tage_snapshot(token,resolved=True).wanted)
        self.check((True,self.program.provider_counter),
            (bool(fields[f'{slot}.has_provider']),fields[f'{slot}.counter']),
            'real TAGE experience remains fixed while SC learns')
        return slot,value

    def begin_context_feedback(self,receipt,taken,label):
        from bpuverify.bpu.model.pipeline import Resolution
        self.check(None,self.probe,'one completed original before another feedback')
        token,value=self.context_source(receipt)
        resolution=Resolution(token.history,token.pc,
            (self.program.outcome(token,value.late,taken),),origin=token)
        feedback=self.bank.sc_feedback(resolution,True)
        self.probe=dict(label=label,source=token,resolution=resolution,needs_read=feedback_needs_read(feedback),
            writes=label!='used-correct',reads=len(self.context_reads),offers=len(self.context_offers),
            accepts=len(self.context_accepts),before=(deepcopy(self.bank.sc.memory),self.bank.sc.thresholds.values))

    def checked(self,tick,*args):
        super().checked(tick,*args)
        self.invalid_history.observe(self.pipeline,self.cycle,self.observed['statistical'],tick,self.check)
        warm=self.warm_query
        first=self.cycle.tokens[0]
        if (warm is not None and not warm['future'].done() and first is not None
                and first.pc==self.program.jump and self.cycle.fires[1] and not self.cycle.flushes[0]):
            self.check(False,self.cycle.decisions[0].branch.taken,
                'the normal Main jump correction issues the warm query after prediction flow closes')
            warm['future'].set_result(self.pipeline.current_event)
        if warm is not None and warm['token'] is None and self.cycle.fires[0]:
            token=self.pipeline.model.stages[0]
            read=self.bank.statistical_snapshot(token).read
            if (token.pc==warm['pc'] and self.bank.read_enabled.get(token.history.sequence,False)
                    and read.context.common_valid and read.indices[1:3]==warm['indices']
                    and all(any(values) for values in read.weights[1:3])):
                warm['token']=token
        probe=self.probe
        if probe is None:return
        request=self.events.feedback
        feedback=self.bank.sc_feedback(request,True) if request is not None else None
        needed=feedback is not None and feedback_needs_read(feedback)
        context=Context() if feedback is None else Context.from_history(feedback.history)
        bank,indices=coordinates(0 if feedback is None else feedback.pc,context)
        actual=self.observed['statistical']['accepted_reads']
        for table,(family,port) in enumerate(zip(FAMILIES,actual,strict=True)):
            active=needed and (context.common_valid or family not in ('global','backward'))
            self.check(active,bool(port['valid']),'actual SC read respects original qualification for every family')
            if active:
                self.check((indices[table],1<<bank),(port['index'],port['bank']),
                    'actual training read belongs to original nonzero context')
        if needed:
            self.context_reads.append(dict(tick=tick,owner=request.origin.sequence,ports=deepcopy(actual)))
        if request is not None:
            self.check(True,request.origin is probe['source'],'accepted context feedback owns its exact published original')
            self.check(probe['resolution'].branches,tuple(b for b in request.branches if b is not None),
                'accepted executed outcome remains the declared instruction truth')
            self.context_accepts.append(tick)
        if self.expected_patches:
            self.check(tuple(range(len(FAMILIES))),tuple(patch[0] for patch in self.expected_patches),
                'all five independent feature families produce compared learning effects')
            self.context_offers.append(dict(tick=tick,patches=self.expected_patches))

    def end_context_feedback(self,request):
        probe=self.probe
        self.check(True,request.origin is probe['source'],'driver result keeps the accepted context original')
        self.check(1,len(self.context_accepts)-probe['accepts'],'one actual acceptance of this original')
        self.check(int(probe['needs_read']),len(self.context_reads)-probe['reads'],'read or suppression follows original qualification')
        self.check(int(probe['writes']),len(self.context_offers)-probe['offers'],'read-only and five-family learning remain distinct')
        if not probe['writes']:
            self.check(probe['before'],(self.bank.sc.memory,self.bank.sc.thresholds.values),
                'sufficiently confident correct feedback preserves every weight and threshold')
            self.check(not self.program.agrees,probe['needs_read'],'correct SC reads only when original TAGE disagrees')
            self.mark('correct-feedback-qualification')
        elif probe['label']=='used-wrong':
            self.check(True,probe['needs_read'],'wrong used SC must read and learn')
            self.mark('wrong-feedback-learning')
        self.receipts.append(dict(label=probe['label'],owner=probe['source'].sequence,
            accepted=self.context_accepts[-1],needs_read=probe['needs_read'],five_family_learning=probe['writes']))
        self.probe=None

    def finish_context(self,consumers):
        self.pipeline.raise_failure()
        self.check(None,self.probe,'all context feedback completed before checking closure')
        self.check(('teaching-0','teaching-1','teaching-2','teaching-3','used-correct','used-wrong'),
            tuple(row['label'] for row in self.receipts),'complete instruction experience and both used-feedback classes')
        self.check(5,len(self.context_offers),'four cold originals and one wrong-used original learn all five families')
        self.check(5+int(not self.program.agrees),len(self.context_reads),'all required accepted five-family reads compared')
        self.check(4,len({self.save(source).sequence for source in self.originals}),'distinct original teaching evidence')
        for receipt,token,snapshots,metadata in self.saved.values():
            self.check(True,self.pipeline.source_token(receipt) is token,'exact public original is retained')
            self.check(snapshots,self.snapshots(token),'all nine original evidence domains remain immutable')
            self.check(metadata,receipt.meta,'public original metadata remains immutable')
        self.mark('distinct-teaching-originals')
        self.mark('all-five-learning-effects')
        self.mark('fresh-after-both-feedbacks')
        self.mark('immutable-original-evidence')
        result=dict(profile=self.program.profile,receipts=self.receipts,
            numeric_consumers=[self.numeric_consumer(source) for source in consumers],
            numeric_prediction_checks={key:value for key,value in self.pipeline.counts.items() if key.startswith(('sc-numeric-','sc-composition-'))},
            history=dict(valid=True,ghr=1,bw=int(self.program.backward)),
            real_prefix=True,independent_query_history=True,five_families=FAMILIES,
            actual_training_reads=self.context_reads,compared_learning_offers=self.context_offers,
            consumers=[dict(owner=self.save(source).sequence,
                scores=self.bank.statistical_snapshot(self.save(source),resolved=True).prediction.sums)
                for source in consumers],
            original_sources=len(self.saved),all_original_domains_immutable=True,
            TAGE_held_by_normal_enable_during_SC_feedback=True,complete_FTQ=False,no_bank_sweep=True)
        self.check({'global','backward'},set(self.invalid_history.witnesses),
            'both history families need a real nonzero stale response and the same query neutral consumption')
        self.check(True,self.invalid_history_probe is not None,'the declared cancelled warm query completed normally')
        probe=self.invalid_history_probe
        for family,weights in zip(('global','backward'),probe['warm_history_weights'],strict=True):
            witness=self.invalid_history.witnesses[family]
            self.check(probe['invalid_consumer']['owner'],witness['owner'],
                'the declared post-cancellation consumer owns this stale-response witness')
            self.check(True,probe['warm_read_tick']<witness['issued_tick'],
                'the witness follows a genuinely learned warm query, not random reset data')
            self.check(weights,witness['raw_weights'],'actual old response retains the independently compared warm experience')
        for family in ('global','backward'):self.mark('stale-'+family+'-experience-masked')
        result['invalid_history_masking']=self.invalid_history.witnesses
        result['cancelled_warm_query']=self.invalid_history_probe
        self.coverage.finish()
        return result


class ConcurrentContextChecks(ContextChecks):
    """The same five-family oracle, plus actual input ownership under contention."""
    def __init__(self,profile,coverage):
        from bpuverify.bpu.model.statistical_prefix import ConcurrentContextLayout
        super().__init__(profile,coverage,layout_type=ConcurrentContextLayout)
        self.stream=False
        self.steady=0
        self.arbitrations=[]
        self.arbitration=None

    def candidates(self,row,*args):
        super().candidates(row,*args)
        self.training=row['inputs']['training']
        return ()

    def begin_context_feedback(self,receipt,taken,label):
        super().begin_context_feedback(receipt,taken,label)
        self.check(None,self.arbitration,'previous concurrent feedback has completed')
        self.arbitration=dict(label=label,owner=self.probe['source'].sequence,
            needs_read=self.probe['needs_read'],blocked=0,overlap=0,payload=None,accepted=None)

    def checked(self,tick,*args):
        super().checked(tick,*args)
        c,p=self.cycle,self.program
        stable=(self.stream and all(t is not None and t.pc==p.loop for t in c.tokens)
            and all(c.fires) and not any(c.flushes) and not c.middle_repair and not c.final_repair
            and all(choice.branch.target==p.loop for choice in c.decisions))
        self.steady=self.steady+1 if stable else 0
        probe=self.arbitration
        if probe is None or not self.training['valid']:return
        payload={key:deepcopy(value) for key,value in self.training.items() if key not in ('valid','ready')}
        if probe['payload'] is None:probe['payload']=payload
        self.check(probe['payload'],payload,'complete old feedback stays unchanged while newer predictions run')
        if c.fires[0]:
            self.check(p.loop,c.next_pc,'concurrent prediction is the separately learned instruction stream')
            lookup=self.observed['statistical']['lookup']
            self.check((True,0,0),(bool(lookup['valid']),lookup['ghr'],lookup['bw']),
                'new valid-zero-history stream cannot replace old valid nonzero feedback history')
            probe['overlap']+=1
        if not self.observed['statistical']['ready']:
            self.check(True,p.blocks(probe['needs_read']),'only qualified same-resource feedback must wait')
            self.check(False,bool(self.training['ready']),'SC denial holds the complete input')
            self.check(None,probe['accepted'],'held feedback has not already been accepted')
            self.check(self.probe['before'],(self.bank.sc.memory,self.bank.sc.thresholds.values),
                'unaccepted old feedback cannot change learned experience or thresholds')
            probe['blocked']+=1
        if self.events.feedback is not None:
            self.check(None,probe['accepted'],'concurrent old original is accepted exactly once')
            self.check(not p.blocks(probe['needs_read']),bool(c.fires[0]),
                'actual acceptance follows release or coexists with independent prediction')
            probe['accepted']=tick

    def end_concurrent_feedback(self,request,accepted):
        probe=self.arbitration
        self.check(True,probe['overlap']>0,'every feedback submission overlaps actual prediction')
        self.check(self.program.blocks(probe['needs_read']),probe['blocked']>0,
            'waiting is determined by original read need and actual resource relation')
        if self.program.blocks(probe['needs_read']):
            self.check(True,probe['blocked']>=2,'held complete original survives repeated actual denial')
        self.check(accepted.tick,probe['accepted'],'driver receipt equals actual monitor acceptance')
        self.end_context_feedback(request)
        self.arbitrations.append({key:value for key,value in probe.items() if key!='payload'})
        self.arbitration=None

    def finish_context(self,consumers):
        self.check(None,self.arbitration,'all concurrent driver transfers have completed')
        self.check(6,len(self.arbitrations),'all four cold, correct-used and wrong-used feedbacks overlap prediction')
        self.check(tuple(row['label'] for row in self.receipts),tuple(row['label'] for row in self.arbitrations),
            'all original learning classes have complete concurrent ownership evidence')
        for rule in ('old-context-survives-new-predictions','qualification-controls-waiting',
                'complete-feedback-accepted-once'):self.mark(rule)
        result=super().finish_context(consumers)
        result.update(concurrent_original_feedback=self.arbitrations,
            current_stream_history=dict(valid=True,ghr=0,bw=0),original_feedback_history_nonzero=True,
            serial_and_concurrent_learning_oracle_identical=True)
        return result
