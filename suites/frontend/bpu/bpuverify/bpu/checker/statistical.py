"""Independent SC reads, feedback obligations and complete signed write patches."""
from bpuverify.sc.checker.semantic import prediction_values
from bpuverify.sc.model.semantic import feedback_needs_read,FAMILIES


def numeric_origins(sources,cycle,previous):
    """Only independently accepted requests create a new response obligation.

    A held SRAM output may be reused by a training read. Do not compare it on
    every held cycle; the subsequent consumed evidence must still belong to
    the original S0 snapshot. Never search nearby phases for agreeing data.
    """
    if previous is None:return {}
    result={}
    if previous.enabled[2] and previous.enabled[4]:
        for name,slot,issued in (('read',0,previous.fires[0]),
                ('consume',1,previous.fires[1] and not previous.flushes[0])):
            token=cycle.tokens[slot]
            if issued and token is not None and sources.read_enabled.get(token.history.sequence,False):
                sources.statistical_snapshot(token)  # Enforce exact original lifetime.
                result[name]=token
    return result


def signed_value(value,width):
    if type(value) is not int or not 0<=value<1<<width:
        raise ValueError(f'expected an unsigned {width}-bit sampled value')
    return value-(1<<width) if value>=(1<<(width-1)) else value


class InvalidHistoryEvidence:
    """A discriminating raw-port witness, never an input to the reference.

    Unrequested SRAM outputs are unspecified. Only their nonzero presence is
    useful here: the independently owned invalid query must still consume
    neutral history weights. Both numerical boundaries must already compare.
    """
    def __init__(self):
        self.requests = {}
        self.pending = {}
        self.witnesses = {}
        self.after_tick = None

    def begin_window(self,after_tick):
        """Exclude reset/random port contents and all preparation responses."""
        self.requests.clear()
        self.pending.clear()
        self.witnesses.clear()
        self.after_tick=after_tick

    def observe(self,pipeline,cycle,actual,tick,check):
        if self.after_tick is None or tick<=self.after_tick or len(self.witnesses)==2:return
        sources=pipeline.model.sources
        if cycle.fires[0]:
            issued=pipeline.model.stages[0]
            if issued is not None and sources.read_enabled.get(issued.history.sequence,False):
                read=sources.statistical_snapshot(issued).read
                if not read.context.common_valid:
                    self.requests[issued.history.sequence]=(issued.history,tick,tuple(map(bool,actual['prediction_requests'])))
        for phase,token in numeric_origins(sources,cycle,pipeline.sc_previous_cycle).items():
            read=sources.statistical_snapshot(token).read
            if read.context.common_valid:continue
            key=token.history.sequence
            proof=pipeline.sc_numeric_checked.get(key,{})
            check(tick,proof.get(phase),'invalid-history witness requires the actual numeric boundary comparison')
            if phase=='read':
                request=self.requests.pop(key,None)
                check(True,request is not None and request[0] is token.history,
                    'the invalid response belongs to an actually observed original request')
                _,issued_tick,valids=request
                check((False,False),(valids[1],valids[2]),'neither history family issued an actual prediction read')
                check(True,issued_tick<tick,'actual request observation precedes the raw response')
                raw={family:tuple(signed_value(value,6) for value in actual['prediction_read']['words'][table])
                     for table,family in ((1,'global'),(2,'backward'))}
                raw={family:values for family,values in raw.items() if any(values)}
                if raw:self.pending[key]=(token.history,token.sequence,issued_tick,tick,raw)
            elif key in self.pending:
                owner,sequence,issued_tick,read_tick,raw=self.pending.pop(key)
                check(True,owner is token.history,'raw response and consumption own the exact same query')
                check(read_tick,proof.get('read'),'raw witness has the same independently compared read boundary')
                check(True,read_tick<tick,'raw response must precede its consumption')
                completed={}
                for table,family in ((1,'global'),(2,'backward')):
                    if family not in raw:continue
                    consumed=tuple(signed_value(value,7) for value in actual['prediction_evidence']['words'][table])
                    check((1,)*len(raw[family]),consumed,'invalid history consumes neutral weights despite nonzero old '+family+' response')
                    completed[family]=dict(owner=sequence,history_owner=key,pc=token.pc,
                        issued_tick=issued_tick,read_tick=read_tick,consumed_tick=tick,raw_weights=raw[family],
                        consumed_percsum=consumed,history_valid=False,
                        actual_history_prediction_request_suppressed=True,
                        original_numeric_read_and_consumption_compared=True)
                for family,witness in completed.items():self.witnesses.setdefault(family,witness)
        self.pending={key:value for key,value in self.pending.items() if key in sources.read_enabled}
        self.requests={key:value for key,value in self.requests.items() if key in sources.read_enabled}


def numeric_values(sources,token,actual,*,consumed=False):
    read=sources.statistical_snapshot(token).read
    expected=dict(indices=read.indices)
    observed=dict(indices=tuple(actual['indices']))
    if not consumed:
        expected['history_valid']=read.context.common_valid
        observed['history_valid']=bool(actual['history_valid'])
    for table,(family,weights) in enumerate(zip(FAMILIES,read.weights,strict=True)):
        if not consumed and not read.context.common_valid and family in ('global','backward'):
            # No request was made. The old raw port is unspecified; hardware
            # zeroing is checked in consumed evidence, not simulated here.
            continue
        expected[family]=tuple(2*value+1 for value in weights) if consumed else weights
        observed[family]=tuple(signed_value(value,7 if consumed else 6) for value in actual['words'][table])
        if not consumed:
            expected[family+'.bank']=1<<(token.pc%2)
            observed[family+'.bank']=actual['banks'][table]
    return expected,observed


def composition_values(sources,token,actual,*,tage_enabled):
    """Exact signed confidence from one original read, not sampled addends.

    All four feature objects and sixteen bias alternatives are defined even
    when Main has no branch. Only the final branch-selected mux has undefined
    absent-slot payload. Its mask comes from independent semantic candidates.
    The existing TAGE decision is pure: no predictor or selector advances.
    """
    from bpuverify.sc.model.semantic import way,bias_feature
    from bpuverify.sc.transaction.types import ScBaseBranch
    read=sources.statistical_snapshot(token).read
    sums=tuple(sum(2*weights[column]+1 for weights in read.weights[:4]) for column in range(4))
    candidates=tuple(tuple(total+2*read.weights[4][4*column+bias]+1 for bias in range(4))
        for column,total in enumerate(sums))
    branches,tagged,_=sources.tage_decision(token,enabled=tage_enabled)
    selected={}
    for slot,branch in enumerate(branches):
        if branch is None:continue
        provider=ScBaseBranch(branch.position,tagged.get(f'{slot}.counter',0),
            int(bool(tagged.get(f'{slot}.has_provider'))))
        selected[str(slot)]=candidates[way(branch.position)][bias_feature(provider)]
    expected=dict(history_sums=sums,candidates=candidates,selected=selected)
    observed=dict(history_sums=tuple(signed_value(value,9) for value in actual['history_sums']),
        candidates=tuple(tuple(signed_value(value,10) for value in row) for row in actual['candidates']),
        selected={slot:signed_value(actual['selected'][int(slot)],10) for slot in selected})
    return expected,observed


def history_values(sources, token, actual):
    source = sources.queries.snapshot(token)
    expected = dict(source.metadata.mapping(), imli=source.loop)
    return expected, {key: actual[key] for key in expected}


def metadata_values(sources, token, actual):
    source = sources.statistical_snapshot(token, resolved=True)
    if not source.enabled:
        # Disabled SC metadata holds an older payload; it is not this query's
        # independently defined read and cannot be compared as a fresh one.
        return {}, {}
    expected, observed = prediction_values(source.prediction, actual)
    # Main has no branch at an absent slot. Its position payload is then
    # unspecified, so so are the indexed weight sign, bias and unused sum.
    # Never gate a real comparison with sampled DUT validity: these owners
    # come exclusively from the independent original Main read. The absence
    # of SC authority/provider validity remains checkable for *every* slot.
    defined = tuple(slot for slot, branch in enumerate(source.branches) if branch is not None)
    for key, value in tuple(expected.items()):
        if isinstance(value, tuple) and key not in ('useScPred', 'tagePredValid', 'sumAboveThres'):
            slots=defined
            if key in ('tageCtr','tagePred'):
                # Sc.scala registers raw provider bits separately from valid.
                # Invalid bits neither select bias nor authorize learning and
                # are not required to clear when TAGE reads are disabled.
                # Only independently predicted validity defines this mask;
                # the actual validity/authority/bias remain fully compared.
                slots=tuple(slot for slot in defined if source.prediction.branches[slot].provider_valid)
            expected[key] = {str(slot): value[slot] for slot in slots}
            observed[key] = {str(slot): observed[key][slot] for slot in slots}
    return expected, observed


def live_values(sources, events, cycle, actual):
    step = sources.preview_history(events, cycle)
    # These are post-edge T1 threshold/T2 offer outputs. The write buffer
    # consumes the offer on the following edge; its model remains unadvanced.
    patches, thresholds = sources.sc.preview_learning()
    expected = dict(state=sources.queries.value.mapping(), lookup=step.lookup.mapping(),
        loop_state=sources.queries.iterations.cursor, loop_lookup=step.iteration.after,
        thresholds=tuple(thresholds))
    observed = {key: actual[key] for key in expected}
    prediction=bool(cycle.enabled[2] and cycle.enabled[4] and cycle.fires[0])
    expected['prediction_requests']=tuple(prediction and (step.lookup.valid or family not in ('global','backward'))
        for family in FAMILIES)
    observed['prediction_requests']=tuple(map(bool,actual['prediction_requests']))
    pending = {table: (bank, index, patch) for table, bank, index, patch in patches}
    for table, row in enumerate(actual['updates']):
        active = bool(row['valid'] and any(row['mask']))
        key = f'update.{table}'
        wanted = pending.get(table)
        expected[key + '.active'], observed[key + '.active'] = wanted is not None, active
        if wanted is not None:
            bank, index, patch = wanted
            expected[key + '.identity'] = (1 << bank, index, tuple(int(v is not None) for v in patch))
            observed[key + '.identity'] = (row['bank'], row['index'], tuple(row['mask']))
            for column, value in enumerate(patch):
                if value is not None:
                    expected[f'{key}.{column}'], observed[f'{key}.{column}'] = value, row['data'][column] - 64 if row['data'][column] >= 32 else row['data'][column]
    return expected, observed


def readiness(sources, cycle, resolution):
    enabled = bool(cycle.enabled[2] and cycle.enabled[4])
    transaction = sources.sc_feedback(resolution, enabled)
    conflict = (transaction is not None and feedback_needs_read(transaction)
        and cycle.fires[0] and cycle.next_pc % 2 == transaction.pc % 2)
    return not conflict
