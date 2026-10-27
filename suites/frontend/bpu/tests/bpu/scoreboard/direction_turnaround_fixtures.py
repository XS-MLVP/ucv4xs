"""Owned logical events plus synthetic observations; never DUT evidence."""
from concurrent.futures import Future
from dataclasses import replace
from types import SimpleNamespace as NS

from toffee import XEvent,XEventKind,XPhase

from bpuverify.bpu.checker.direction_turnaround import DirectionTurnaroundChecks
from bpuverify.bpu.coverage.direction_turnaround import DirectionTurnaroundCoverage
from bpuverify.bpu.model.pipeline import Redirect
from bpuverify.bpu.model.tage.asymmetric_retirement import OUTCOMES,PRELUDE_PLAN
from bpuverify.bpu.model.tage.mixed_visibility import PARTIAL_PLAN,FIRST_SERVICE
from bpuverify.bpu.model.tage.neighbor_migration import PC,HISTORY_PATHS
from bpuverify.bpu.model.tage.service import STREAM_PC
from tests.bpu.scoreboard.test_neighbor_migration import fixture
from tests.bpu.scoreboard.test_dual_migration import source
from tests.bpu.scoreboard.test_direction_sources import quiet
from tests.bpu.scoreboard.test_direction_service import via,streaming_query
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_mixed_visibility_model import mature
from tests.bpu.scoreboard.asymmetric_retirement_fixtures import packet as initial_packet
from tests.bpu.scoreboard.mixed_visibility_fixtures import packet
from tests.bpu.scoreboard.test_partial_reuse import transfer


def consumers(checks,reference,phase):
    model,event,anchor=reference
    for i,(name,path) in enumerate(HISTORY_PATHS.items()):
        if phase=='serviced':token=via(model,event,anchor,path)
        else:
            mid=streaming_query(model,event,anchor.history,path,anchor.pc+4)
            token=streaming_query(model,event,mid.history,PC,path+4)
        tick=dict(initial=100040,mixed=100200,blocked=100500,serviced=100800)[phase]+20*i
        checks.consume(phase,name,source(model,token,tick))


def armed(program,*,checks_type=DirectionTurnaroundChecks,coverage_type=DirectionTurnaroundCoverage,initial_pc=None):
    checks,(model,event,anchor),retired=fixture(
        initial_pc=initial_pc,checks_type=lambda p,c:checks_type(p,c,program),
        coverage_type=lambda:coverage_type(program))
    warm=source(model,via(model,event,anchor,HISTORY_PATHS['original']),80000)
    request=resolution(warm.token,OUTCOMES[1])
    model.advance(replace(quiet(model,event),feedback=request))
    current={n:source(model,via(model,event,anchor,p),81000+20*i)
             for i,(n,p) in enumerate(HISTORY_PATHS.items())}
    checks.arm_asymmetric(warm,(80020,request),current)
    return checks,(model,event,anchor),retired


def mixed(program,*,checks_type=DirectionTurnaroundChecks,coverage_type=DirectionTurnaroundCoverage,
          packet_factory=packet,initial_pc=None):
    checks,reference,retired=armed(program,checks_type=checks_type,coverage_type=coverage_type,initial_pc=initial_pc)
    model,event,anchor=reference
    model.advance(replace(quiet(model,event),redirect=Redirect(anchor.history,anchor.pc+4,getattr(checks,'stream_pc',STREAM_PC),True)))
    for _ in range(8):model.advance(event)
    checks.begin_read_window();receipts=[]
    for i,(s,outcome) in enumerate(zip(checks.requests[:3],OUTCOMES[:3],strict=True)):
        tick=100000+2*i;request=resolution(s.token,outcome)
        checks.capture_state(NS(tick=tick),initial_packet(checks,training=True))
        model.advance(replace(event,feedback=request));receipts.append((tick,request))
    mature(model,event)
    for i in range(3):checks.capture_state(NS(tick=100008+2*i),initial_packet(checks,index=i))
    checks.pipeline.last_resolution_controls=100004,event.enabled
    checks.accepted_burst(tuple(receipts));checks.pending()
    consumers(checks,reference,'initial')
    checks.pipeline.last_tick=100090;checks.begin_partial(Future(),Future())
    row=packet_factory(checks,plan=PRELUDE_PLAN);row['state']['reads'][0]['valid']=0
    for owner,p in enumerate(row['state']['writes']):p.update(ready=1,bits=checks.payload(FIRST_SERVICE[owner]))
    prepared=XEvent(event_id=100099,tick=100099,phase=XPhase.DRIVE_STABLE,kind=XEventKind.DRIVE_STABLE)
    checks.prepare_partial(prepared,row)
    model.advance(replace(event,prediction_ready=False))
    for owner in range(2):checks.write_accepted(owner,transfer(100100,checks.payload(FIRST_SERVICE[owner])))
    for _ in range(8):model.advance(event)
    checks.capture_state(NS(tick=100102),packet_factory(checks,plan=PARTIAL_PLAN))
    checks.pipeline.last_tick=100102;checks.partial_complete(checks.partial_receipt.result())
    consumers(checks,reference,'mixed')
    return checks,reference,retired


def relearned(program,*,missing_last=False,**options):
    checks,reference,retired=mixed(program,**options)
    model,event,_=reference;checks.arm_mixed();receipts=[]
    for i,(s,outcome) in enumerate(zip(checks.requests[3:],program.late_outcomes,strict=True)):
        tick=100400+2*i;request=resolution(s.token,outcome)
        checks.capture_state(NS(tick=tick),packet(checks,training=True))
        model.advance(replace(event,feedback=request));receipts.append((tick,request))
    mature(model,event)
    count=len(program.late_sources)-int(missing_last)
    for i in range(count):
        checks.capture_state(NS(tick=100408+2*i),packet(checks,index=3+i,plan=program.pending_before(i)))
    checks.pipeline.last_resolution_controls=receipts[-1][0],event.enabled
    checks.accepted_burst(tuple(receipts))
    return checks,reference,retired


def released(program,**options):
    checks,reference,retired=relearned(program,**options);checks.pending()
    consumers(checks,reference,'blocked')
    checks.pipeline.last_tick=100600;checks.release()
    return checks,reference,retired


def completed(program,**options):
    checks,reference,retired=released(program,**options)
    for owner,versions in enumerate(checks.expected_plan):
        for i,payload in enumerate(versions):checks.write_accepted(owner,transfer(100610+2*i,payload))
    checks.services_complete();quiet(reference[0],reference[1])
    consumers(checks,reference,'serviced')
    return checks,reference,retired
