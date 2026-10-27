"""Few actual sources, complete transport, normal driver and service monitors."""
from copy import deepcopy
from hashlib import sha256
import json
from bpuverify.bpu.bundle.main_service import main_service_binding
from bpuverify.bpu.env.main_service import branch
from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.model.main_service import observed_counter,entry_payload
from bpuverify.bpu.monitor.service import ServiceMonitor
from bpuverify.mbtb.model.semantic import Entry,Target,coordinate,tag
from bpuverify.bpu.env.bounded_sources import bounded_program
from bpuverify.bpu.model.feedback_gate import wire_payload
from bpuverify.bpu.model.miss_authority import PC,FOREIGN_PC,STREAM_PC,RESIDENT_POSITION,RULES
from bpuverify.bpu.checker.miss_authority import Checks


async def run(agent,p,coverage,evidence):
    env=observer=None;originals=[]
    fingerprint=lambda value:sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
    try:
        async with bounded_program(agent,late_enabled_at_boot=True) as (env,helper):
            await env.teach(helper,branch(12,STREAM_PC,2,wrong=True))
            resident=await env.capture_source(PC)
            originals.append((resident,deepcopy(resident.meta.resolve),deepcopy(resident.meta.redirect)))
            await env.teach(resident,branch(RESIDENT_POSITION,STREAM_PC,1,wrong=True))
            coverage.reach('normally-learned-resident')
            cold=await env.capture_source(FOREIGN_PC)
            originals.append((cold,deepcopy(cold.meta.resolve),deepcopy(cold.meta.redirect)))
            token=env.checker.source_token(cold)
            observer=Checks(env,p)
            observer.snapshots=list(originals)
            observer.check(False,any(s.hit for row in source_entries(token.lookup) for s in row),'new logical tag is an actual original Main miss')
            literal=deepcopy(cold.meta.resolve['mbtb_entries'])
            observer.check(False,any(s['rawHit'] for row in literal for s in row),'all raw hit bits really exclude the old identity')
            witness=literal[0][1]
            observer.check((0,RESIDENT_POSITION,1,2),
                (witness['rawHit'],witness['position'],witness['attribute']['branchType'],witness['counter_value']),
                'counterexample precondition: genuine miss retains an old conditional position/counter without fabricating it')
            observer.check(0,cold.prediction.taken,'cold final guidance is not taken, so the declared update-only outcome is not a hidden correction')
            evidence.update(original_literal_main=literal,semantic_main=tuple(tuple(dict(hit=s.hit,position=s.position,kind=s.kind,counter=s.counter)
                for s in row) for row in source_entries(token.lookup)),original_source=token.sequence,
                source_tick=cold.meta_tick,active_before_input=len(env.checker.windows.ledger.active))
            coverage.reach('actual-original-cold-miss',source=token.sequence)
            async with ServiceMonitor(agent,observer,binding=main_service_binding(agent,alignment=0,bank=0)):
                tx=env.prepare_feedback(cold,branch(p.position,STREAM_PC,1,taken=bool(p.taken),wrong=p.allocate))
                expected=deepcopy(wire_payload(tx))
                event=await env.send_input(cold,tx)
                await env.observation.wait('all_actual_main_service_witnesses_delivered',lambda _:observer.completed_services())
                observer.check(1,len(observer.literal_inputs),'one complete literal original input accepted')
                observer.check(expected,observer.literal_inputs[0]['payload'],'all input fields including unqualified payload were returned unchanged')
                observer.check(event.tick,observer.literal_inputs[0]['tick'],'literal packet belongs to the exact prepared acceptance')
                coverage.reach('complete-literal-feedback-once',accepted=event.tick)
                env.checker.windows.ledger.live(env.checker.receipt_window(cold))
                coverage.reach('source-lifetime-qualified',active=len(env.checker.windows.ledger.active))
                evidence.update(input_tick=event.tick,input_payload_sha256=fingerprint(observer.literal_inputs[0]['payload']),
                    expected_input_payload_sha256=fingerprint(expected),
                    accepted_literal_main=deepcopy(observer.literal_inputs[0]['payload']['meta']['mbtb_entries']),
                    directions=deepcopy(observer.directions),counter_services=deepcopy(observer.written[2]),
                    entry_proposals=deepcopy(observer.incoming),entry_services=deepcopy(observer.written[:2]))
                effect=entry_payload(coordinate(FOREIGN_PC)[2],Entry(tag(FOREIGN_PC),p.position,1,0,Target.encode(FOREIGN_PC,STREAM_PC)))
                expected_entries=[effect] if p.allocate else []
                observer.check(expected_entries,[r['bits'] for r in observer.incoming],'only requested new identity gets an entry proposal')
                observer.check((expected_entries,[]),tuple([r['bits'] for r in rows] for rows in observer.written[:2]),
                    'actual new entry services on its independent selected owner')
                coverage.reach('entry-allocation-ownership')
                proposed=[observed_counter(r['bits']) for r in observer.directions]
                serviced=[observed_counter(r['bits']) for r in observer.written[2]]
                wanted=[] if p.direction is None else [p.direction]
                observer.check(wanted,proposed,'a miss has no resident direction authority; allocation resets only its new owner')
                coverage.reach('direction-authority')
                observer.check(wanted,serviced,'actual SRAM direction services preserve the old unhit resident')
                coverage.reach('actual-direction-service')
                consumer=await env.capture_source(PC)
                owner=env.checker.source_token(consumer)
                actual=[(s.position,s.kind,s.counter) for row in source_entries(owner.lookup) for s in row if s.hit]
                observer.check([(RESIDENT_POSITION,1,2)],actual,'fresh old identity retains its direction and logical branch')
                if p.allocate:
                    fresh=await env.capture_source(FOREIGN_PC);owner=env.checker.source_token(fresh)
                    actual=[(s.position,s.kind,s.counter) for row in source_entries(owner.lookup) for s in row if s.hit]
                    observer.check([(p.position,1,2)],actual,'fresh new identity owns weak taken initialization')
                coverage.reach('fresh-independent-consumers')
                observer.check(True,all(s.meta.resolve==resolve and s.meta.redirect==redirect for s,resolve,redirect in originals),
                    'original full snapshots remain immutable')
                coverage.reach('immutable-original-metadata');coverage.finish();observer.status='PASS'
                evidence.update(status='PASS',completed=list(RULES),independent_consumers_checked=True)
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error)[:6000],
            first_differences=[dict(path=d.path,expected=repr(d.expected),actual=repr(d.actual)) for d in getattr(error,'differences',())[:12]])
        raise
    finally:
        if observer is not None:evidence['service_summary']=observer.summary()
        if env is not None:
            evidence.update(actual_qualified_inputs=env.checker.actual_inputs,all_actual_S1=env.checker.windows.counts['S1-admission'],
                peak_live=env.checker.windows.peak,capacity_assumption=8,full_FTQ_reachability_proved=False,
                no_commit_inferred=True,original_pipeline_and_PHR_checks_active=True,
                source_ledger=env.checker.windows.ledger.state(),
                original_snapshots_unchanged=all(s.meta.resolve==resolve and s.meta.redirect==redirect for s,resolve,redirect in originals))
