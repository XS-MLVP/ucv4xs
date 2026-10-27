#!/usr/bin/env python3
"""Exact registered exception payload invariant; never dynamic coverage gain."""
from bisect import bisect_right
from collections import Counter,defaultdict
from itertools import product
import hashlib
import json
from pathlib import Path
import re

from audit_coverage_points_v1 import records,sha256_file
from audit_evidence_io import write_report
from audit_gap_closure_v1 import native,digest_keys,point_key
from audit_initial_branch_boundaries_v1 import initial_region
from audit_load_raw_owners_v1 import FULL
from audit_sq_head_permit_domain_v1 import source,evidence

ROOT=Path(__file__).resolve().parents[1]
BITS=(23,19,15,7,6)
PAYLOAD=re.compile(r'uop_\d+_exceptionVec_(23|19|15|7|6):(0->1|1->0)')


def compact(text):return re.sub(r'\s+','',text)


def source_proof(dut):
    path=ROOT/'dut'/dut/'LoadQueueReplayDut.v' if dut=='load_queue_replay' else ROOT/'rtl'/dut/'LoadQueueReplay.sv'
    pinned=json.loads((ROOT/'rtl'/dut/'source.json').read_text())['files']
    assert pinned['LoadQueueReplay.sv']==sha256_file(path)
    raw=path.read_text();newlines=[m.start() for m in re.finditer('\n',raw)]
    defs={name:compact(rhs) for name,rhs in re.findall(r'\bwire\s+(\w+)\s*=\s*([^;]+);',raw)}
    names_for_rhs=defaultdict(list)
    for name,rhs in defs.items():names_for_rhs[rhs].append(name)
    declared=re.findall(r'\breg\s+(uop_\d+_exceptionVec_(?:23|19|15|7|6))\s*;',raw)
    expected={f'uop_{index}_exceptionVec_{bit}' for index in range(120) for bit in BITS}
    assert set(declared)==expected and len(declared)==600
    writes={name:[] for name in declared};initial=[]
    assignment=r'\b(uop_\d+_exceptionVec_(?:23|19|15|7|6))\s*(<=|=(?!=))\s*([^;]+);'
    for match in re.finditer(assignment,raw):
        name,operator,rhs=match.groups();line=bisect_right(newlines,match.start())+1
        region=initial_region(str(path),line)
        if region:
            assert operator=='=' and re.fullmatch(r'\s*_RANDOM\[[^\]]+\]\[\d+\]\s*',rhs)
            initial.append((name,line,region))
        else:
            assert operator=='<='
            writes[name].append((compact(rhs),line,match.start()))
    assert len(initial)==600 and {name for name,_,_ in initial}==expected
    assert all(region==initial[0][2] for _,_,region in initial)
    start=raw.index('  always @(posedge clock) begin\n    if (needEnqueue_2) begin')
    middle=raw.index('    else if (needEnqueue_1) begin',start)
    low=raw.index('    else if (needEnqueue_0) begin',middle)
    h=hashlib.sha256();clock_lines=[]
    for name,items in sorted(writes.items()):
        assert len(items)==3,(name,len(items))
        rhs2,rhs1,rhs0=(item[0] for item in items)
        assert start<items[0][2]<middle<items[1][2]<low<items[2][2]
        bit=name.rsplit('_',1)[1]
        g0=rhs0;assert g0 in defs
        match=re.fullmatch(r'~(\w+)&\(\1\?io_enq_0_bits_uop_exceptionVec_'+bit+':'+name+r'\)',defs[g0])
        assert match,(name,defs[g0]);select0=match[1]
        fallback=names_for_rhs[f'needEnqueue_0?{g0}:{name}'];assert len(fallback)==1
        f0=fallback[0];g1=rhs1;assert g1 in defs
        match=re.fullmatch(r'~(\w+)&\(\1\?io_enq_1_bits_uop_exceptionVec_'+bit+':'+f0+r'\)',defs[g1])
        assert match,(name,defs[g1]);select1=match[1]
        match=re.fullmatch(r'~(\w+)&\(\1\?io_enq_2_bits_uop_exceptionVec_'+bit+r':needEnqueue_1\?'+g1+':'+f0+r'\)',rhs2)
        assert match,(name,rhs2);select2=match[1]
        h.update(json.dumps([name,items,select0,select1,select2,g0,g1,f0]).encode()+b'\n')
        clock_lines.extend(line for _,line,_ in items)
    return dict(dut=dut,source=str(path.relative_to(ROOT)),source_SHA256=sha256_file(path),
        registers=600,all_clocked_writes=1800,clocked_write_line_range=[min(clock_lines),max(clock_lines)],
        exact_three_port_template_SHA256=h.hexdigest(),initial_random_payload_writes=600,
        initial_region=initial[0][2],first_and_last_register_examples=[declared[0],declared[-1]])


def native_inventory(run,dut,proof):
    meta,dat=native(run,dut);path=ROOT/proof['source']
    assert sha256_file(dat)==meta['artifact']['sha256']
    if dut=='load_queue_replay':assert meta['artifact']['build']['files'][str(path)]==proof['source_SHA256']
    points=[p for p in records(dat) if p['t']=='toggle' and p['f']==str(path) and PAYLOAD.fullmatch(p['o'])]
    assert len(points)==1200
    missing={point_key(p) for p in points if not p['hit']}
    return dict(dut=dut,run=run,source=proof['source'],source_SHA256=proof['source_SHA256'],
        native_build_id=meta['artifact']['build']['build_id'],coverage_dat_SHA256=sha256_file(dat),
        total=1200,hit=1200-len(missing),missing=len(missing),missing_point_set_SHA256=digest_keys(missing),
        directions_and_status=[dict(direction=d,hit=hit,count=count) for (d,hit),count in sorted(Counter(
            (p['o'].rsplit(':',1)[1],bool(p['hit'])) for p in points).items())],
        compact_missing_samples=[dict(source_line=int(p['l']),signal=p['o'],hierarchy=p['h']) for p in points if not p['hit']][:4])


def audit():
    checked=0
    for old,n0,n1,n2,s0,s1,s2,in0,in1,in2 in product((0,1),repeat=10):
        g0=(not s0) and (in0 if s0 else old)
        f0=g0 if n0 else old
        g1=(not s1) and (in1 if s1 else f0)
        g2=(not s2) and (in2 if s2 else g1 if n1 else f0)
        actual=g2 if n2 else g1 if n1 else g0 if n0 else old
        expected=old and not (n0 and s0 or n1 and s1 or n2 and s2)
        assert actual==expected
        if not old:assert not actual
        checked+=1
    proofs={dut:source_proof(dut) for dut in ('load_queue_replay','load_queue','lsq_wrapper')}
    assert len({proof['source_SHA256'] for proof in proofs.values()})==1
    rows=[]
    for dut,proof in proofs.items():
        runs=('lsq-progress-regression-15',) if dut=='load_queue_replay' else ('load-response-contributor-regression-02',FULL)
        inventory=[native_inventory(run,dut,proof) for run in runs]
        if len(inventory)==2:
            assert inventory[0]['missing_point_set_SHA256']==inventory[1]['missing_point_set_SHA256']
            assert inventory[0]['hit']==inventory[1]['hit']
        rows.extend(inventory)
    pinned=evidence(*source('mem/lsqueue/LoadQueueReplay.scala'),868,891,
        ['uop(enqIndex).exceptionVec.zeroInit()','vaddr(enqIndex) := enq.bits.vaddr'])
    report=dict(format='lsq-replay-exception-payload-boundary-v1',rows=rows,source_proofs=list(proofs.values()),pinned_Chisel=pinned,
        all_template_boolean_assignments_checked=checked,exact_next_state='old & !(need0&slot0 | need1&slot1 | need2&slot2)',
        proven_boundary='In two-state clocked execution, once an entry exception bit is zero, all later public enqueues keep it zero. A selected valid write zeroes it; reset is not assumed to initialize this payload.',
        classification='POST_FIRST_VALID_WRITE_ZEROED_EXCEPTION_PAYLOAD',native_dynamic_coverage_gain=0,
        verification=dict(all600registers_and1800clocked_writes_per_source_checked=True,all_other_writes_inside_exact_guarded_initial=True,
            pinned_original_source_hashes=True,all1024two_state_template_assignments_checked=True,
            exact_leaf_and_two_parent_native_inventories_checked=True,all_native_points_and_old_hit_counts_retained=True),
        raw_dat_or_metric_denominators_changed=False,unified_regression_classifications_rewritten=False,
        no_claim_all_uncovered_exceptions_unreachable=True,
        limits='Only600registered exception bits at the exact pinned source in each DUT. Startup/randomization may cause counted directions; four-state/fault injection and public S3 exception behavior are not proven. The initial proof does not cover other payloads. Missing points stay in native denominators. This is supplemental source triage, not a functional UT pass or a coverage increase.')
    write_report(ROOT/'results'/FULL/'replay-exception-payload-boundary-v1.json',report)
    print(json.dumps({key:value for key,value in report.items() if key not in ('source_proofs','pinned_Chisel')},indent=2))
    return report


if __name__=='__main__':audit()
