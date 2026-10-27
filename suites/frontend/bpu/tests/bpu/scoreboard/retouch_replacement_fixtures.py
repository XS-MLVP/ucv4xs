"""Normal independent model events and synthetic observations; never DUT credit."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

from toffee import Scoreboard
from bpuverify.bpu.checker.retouch_replacement import RetouchReplacementChecks
from bpuverify.bpu.coverage.retouch_replacement import RetouchReplacementCoverage
from bpuverify.bpu.model.tage.retouch_replacement import AccessRecencySources,READ_STREAM
from bpuverify.bpu.model.tage.forwarding import PC,resolved_path
from bpuverify.bpu.model.tage.service import learning_inflight
from bpuverify.bpu.model.pipeline import Redirect
from bpuverify.bpu.model.direction_sources import HISTORY_PORTS
from tests.bpu.scoreboard.test_direction_forwarding import establish,resolution,values
from tests.bpu.scoreboard.test_direction_service import additional_history,via,streaming_query
from tests.bpu.scoreboard.test_direction_sources import quiet,revisit
from tests.bpu.scoreboard.test_dual_migration import source
from tests.bpu.scoreboard.test_partial_reuse import transfer


def prepared(program,*,initial_pc=PC,coverage_factory=RetouchReplacementCoverage):
    model,event,anchor=establish(sources_factory=AccessRecencySources,initial_pc=initial_pc)
    for path in program.paths[1:]:event=additional_history(model,event,anchor,path)
    warm=revisit(model,event,anchor,PC)
    model.advance(replace(quiet(model,event),feedback=resolution(warm,resolved_path())))
    assert values(model,revisit(model,event,anchor,PC))==((0,3),(1,6))
    tokens=tuple(revisit(model,event,anchor,PC) if program.paths[h] is None else via(model,event,anchor,program.paths[h])
                 for h in program.feedback_order)
    retired=[]
    pipeline=NS(model=model,board=Scoreboard('retouch-replacement'),last_tick=1000,
        source_token=lambda s:s.token,retire_source=retired.append,raise_failure=lambda:None,
        corrections_for_source=lambda s:((s.prediction_tick+2,2),))
    checks=RetouchReplacementChecks(pipeline,coverage_factory(program),program)
    sources=tuple(source(model,token,100+10*i) for i,token in enumerate(tokens))
    checks.arm(sources)
    model.advance(replace(quiet(model,event),redirect=Redirect(anchor.history,anchor.pc+4,READ_STREAM,True)))
    for _ in range(8):model.advance(event)
    checks.begin_read_window()
    return checks,(model,event,anchor),retired


def packet(checks,snapshot,*,input_index=None,proposal=None):
    plan=checks.plan(snapshot)
    incoming=() if proposal is None else checks.expected_offers[proposal]
    histories=(0,)*len(HISTORY_PORTS)
    if input_index is not None:
        token=checks.pipeline.source_token(checks.sources[input_index])
        histories=tuple(token.history.folds()[i] for i in HISTORY_PORTS)
    return dict(state=dict(reset=0,reads=({'valid':1,'mask':1},{'valid':0,'mask':0}),
        prediction=dict(valid=1,ready=1,pc=READ_STREAM),training=dict(valid=int(input_index is not None),ready=1),
        incoming=tuple(dict(valid=int(proposal is not None and incoming[o] is not None),
                            bits={} if proposal is None or incoming[o] is None else deepcopy(incoming[o])) for o in range(2)),
        dirty=tuple(tuple(int(r is not None) for r in checks.program.owner_records(snapshot,o)) for o in range(2)),
        writes=tuple(dict(valid=int(bool(p)),ready=0,bits={} if not p else deepcopy(p[0])) for p in plan)),
        retained=tuple(tuple({} if r is None else dict(shadow=1,**checks.keys[r.history][o],counter=r.counter)
                             for r in checks.program.owner_records(snapshot,o)) for o in range(2)),
        main=tuple(dict(direction=dict(valid=int(input_index is not None and o in checks.program.input_owners(input_index)),
                                      ready=1,bits=dict(qualified=True))) for o in range(2)),
        train_folds=histories)


def learned(program,*,fault=None,initial_pc=PC,coverage_factory=RetouchReplacementCoverage):
    checks,reference,retired=prepared(program,initial_pc=initial_pc,coverage_factory=coverage_factory);model,event,_=reference
    receipts=[]
    for i,s in enumerate(checks.sources):
        for _ in range(32):
            main=model.sources.main
            if main.offered is None and not any(q.pending for q in main.directions.values()):break
            model.advance(event)
        else:raise AssertionError('independent Main capacity did not become available')
        if i==len(checks.sources)-1 and program.mode=='settled':
            for _ in range(16):
                if not learning_inflight(model.sources.tage):break
                model.advance(event)
            else:raise AssertionError('previous learning did not settle')
        tick=1000+2*i
        if i==len(checks.sources)-1:checks.last_launch=dict(tick=tick-2,learning_inflight=bool(learning_inflight(model.sources.tage)))
        request=resolution(s.token,program.branch_outcomes(i))
        model.advance(replace(event,feedback=request));receipts.append((tick,request))
        checks.capture_state(NS(tick=tick),packet(checks,program.empty_state,input_index=i))
    for _ in range(16):
        model.advance(event)
        if not learning_inflight(model.sources.tage):break
    else:raise AssertionError('new history learning did not mature')
    checks.accepted_burst(tuple(receipts))
    for i,snapshot in enumerate(checks.trace):
        row=packet(checks,checks.before(i),proposal=i)
        if fault is not None:fault(checks,'proposal',i,row)
        checks.capture_state(NS(tick=1100+4*i),row)
        row=packet(checks,snapshot)
        if fault is not None:fault(checks,'effect',i,row)
        checks.capture_state(NS(tick=1102+4*i),row)
    checks.pipeline.last_tick=1200
    checks.capture_state(NS(tick=1200),packet(checks,checks.trace[-1]))
    return checks,reference,retired


def consumers(checks,reference,*,serviced=False):
    model,event,anchor=reference
    for i,path in enumerate(checks.program.paths):
        if serviced:token=revisit(model,event,anchor,PC) if path is None else via(model,event,anchor,path)
        else:
            middle=anchor if path is None else streaming_query(model,event,anchor.history,path,anchor.pc+4)
            token=streaming_query(model,event,middle.history,PC,middle.pc+4)
        receipt=source(model,token,(1500 if serviced else 1250)+20*i)
        (checks.new_consumed if serviced else checks.old_consumed)(receipt)


def released(program,**options):
    checks,reference,retired=learned(program,**options);checks.pending();consumers(checks,reference)
    checks.pipeline.last_tick=1400;checks.release()
    return checks,reference,retired


def completed(program,**options):
    checks,reference,retired=released(program,**options)
    for owner,plan in enumerate(checks.expected_plan):
        for index,payload in enumerate(plan):checks.write_accepted(owner,transfer(1410+2*index,payload))
    quiet(reference[0],reference[1])
    row=packet(checks,checks.trace[-1]);row['state']['reads'][0]['valid']=0
    for p in row['state']['writes']:p.update(valid=0,ready=1)
    checks.capture_state(NS(tick=1490),row)
    consumers(checks,reference,serviced=True)
    return checks,reference,retired
