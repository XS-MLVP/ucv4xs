"""Synthetic checker qualification only; these values never earn DUT credit."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS
from functools import partial

from bpuverify.bpu.checker.confidence_boundary import ConfidenceBoundaryChecks
from bpuverify.bpu.coverage.confidence_boundary import ConfidenceBoundaryCoverage
from bpuverify.bpu.model.pipeline import Redirect
from bpuverify.bpu.model.tage.neighbor_migration import HISTORY_PATHS
from bpuverify.bpu.model.direction_sources import HISTORY_PORTS
from tests.bpu.scoreboard.direction_turnaround_fixtures import mixed as old_mixed,consumers
from tests.bpu.scoreboard.mixed_visibility_fixtures import packet as old_packet
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_partial_reuse import transfer
from tests.bpu.scoreboard.test_mixed_visibility_model import mature


def packet(checks,*,training=False,index=None,plan=None,main=False):
    row=old_packet(checks,training=training,index=index,plan=plan)
    if plan is None:plan=checks.program.final_plan if checks.refill_qualified else checks.program.pending_before(0)
    for port,owner in zip(row['state']['writes'],checks.concrete(plan),strict=True):
        port.update(valid=int(bool(owner)),bits={} if not owner else deepcopy(owner[0]))
    outcome=() if index is None or not main else checks.program.late_outcomes[index-3]
    row['main']=tuple(dict(read=dict(valid=0),direction=dict(
        valid=int(any(i==align for i,_,_ in outcome)),ready=1,bits=dict(qualified=True))) for align in range(2))
    row['train_folds']=(0,)*len(HISTORY_PORTS)
    if training and checks.phase=='refill-holding':
        token=checks.pipeline.source_token(checks.requests[len(checks.input_ticks)])
        row['train_folds']=tuple(token.history.folds()[i] for i in HISTORY_PORTS)
    return row


def mixed(program,*,initial_pc=None,traffic='returning'):
    checks,reference,retired=old_mixed(program,checks_type=partial(ConfidenceBoundaryChecks,traffic=traffic),
        coverage_type=partial(ConfidenceBoundaryCoverage,traffic=traffic),packet_factory=packet,initial_pc=initial_pc)
    model,event,anchor=reference
    # Like the production env, return to the genuine selective-competition
    # loop after observing the mixed versions in all three histories.
    model.advance(replace(event,redirect=Redirect(anchor.history,anchor.pc+4,checks.stream_pc,True)))
    for _ in range(8):model.advance(event)
    return checks,reference,retired


def relearned(program,*,front_fault=None,missing_last=False,traffic='returning'):
    checks,reference,retired=mixed(program,traffic=traffic);model,event,_=reference
    checks.arm_mixed();receipts=[]
    for i,(s,outcome) in enumerate(zip(checks.requests[3:],program.late_outcomes,strict=True)):
        for _ in range(32):
            main=model.sources.main
            if main.offered is None and not any(q.pending for q in main.directions.values()):break
            model.advance(event)
        else:raise AssertionError('independent auxiliary admission did not become eligible')
        tick=100400+2*i;request=resolution(s.token,outcome)
        checks.capture_state(NS(tick=tick),packet(checks,training=True))
        model.advance(replace(event,feedback=request));receipts.append((tick,request))
    mature(model,event)
    for i in range(len(program.late_sources)-int(missing_last)):
        row=packet(checks,index=3+i,plan=program.pending_before(i),main=True)
        if front_fault is not None:front_fault(i,row)
        checks.capture_state(NS(tick=100450+2*i),row)
    checks.pipeline.last_resolution_controls=receipts[-1][0],event.enabled
    checks.accepted_burst(tuple(receipts))
    checks.capture_state(NS(tick=100490),packet(checks,plan=program.final_plan))
    return checks,reference,retired


def released(program,*,traffic='returning'):
    checks,reference,retired=relearned(program,traffic=traffic);checks.pending()
    consumers(checks,reference,'blocked')
    checks.pipeline.last_tick=100600;checks.release()
    return checks,reference,retired


def completed(program,*,traffic='returning'):
    checks,reference,retired=released(program,traffic=traffic)
    for owner,versions in enumerate(checks.expected_plan):
        for i,payload in enumerate(versions):checks.write_accepted(owner,transfer(100610+2*i,payload))
    checks.services_complete();quiet(reference[0],reference[1])
    consumers(checks,reference,'serviced')
    return checks,reference,retired
