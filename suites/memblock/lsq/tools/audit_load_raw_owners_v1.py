#!/usr/bin/env python3
"""Real parent RAW owners and public rollback/refetch, not interface-only CAM."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from audit_checkpoint_pool_v1 import validate_run
from audit_coverage_points_v1 import records,sha256_file,summarize
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases,failure_digest
from audit_gap_closure_v1 import audit as delta,native,point_sets,digest_keys
from audit_load_response_payload_v1 import FULL as BEFORE_FULL,FULL_PATHS
from audit_native_case_probe_v1 import stable_run,journal_streams,xml_node
from audit_native_contributor_scope_v1 import contributors,same_summary
from audit_sq_head_permit_domain_v1 import source,evidence
from audit_store_strict_lifetimes_v1 import source_lines
from audit_uq_page_pairs_v1 import node_summaries
from audit_vsq_release_windows_v1 import line_delta
from run_summary import aggregate

ROOT=Path(__file__).resolve().parents[1]
FULL="load-raw-owners-contributor-regression-02"
PAIRS=(("load_queue","lq-RAW-owners-baseline-02","lq-RAW-owners-after-02"),
       ("lsq_wrapper","lsq-RAW-owners-baseline-02","lsq-RAW-owners-after-02"))
FILES={"load_queue":"tests/load_queue/test_raw_checkpoint_owners.py","lsq_wrapper":"tests/lsq_wrapper/test_raw_checkpoint_owners.py"}
ALL=(1<<64)-1


def load(path):return json.loads(path.read_text())


def pinned_source():
    ranges=[]
    for path,start,end,required in (
        ("mem/lsqueue/LoadQueueRAW.scala",128,183,["enq.ready := Mux(needEnqueue(w), canAccept, true.B)","uop(enqIndex).debugInfo := enq.bits.debugInfo"]),
        ("mem/lsqueue/LoadQueueRAW.scala",194,203,["io.stAddrReadySqPtr.isNotBefore(uop(i).sqIdx)","allocated(i) := false.B"]),
        ("mem/lsqueue/LoadQueueRAW.scala",322,336,["allocated(j) && storeIn(i).valid","datavalid(j)","selectOldestByGroup"]),
        ("mem/lsqueue/LoadQueueRAW.scala",361,397,["TotalSelectCycles","debug_runahead_checkpoint_id := rollbackLqWb(i).bits.debugInfo.runahead_checkpoint_id","io.mdpTrain := Mux1H"]),
        ("mem/pipeline/NewLoadUnit.scala",1089,1106,["nukeQueryReq.dataValid :=","nukeQueryReq.debugInfo := uop.perfDebugInfo","val rawNack = io.rawNukeQueryReq.valid && !io.rawNukeQueryReq.ready"]),
        ("mem/pipeline/NewLoadUnit.scala",1123,1146,["cause(C_RAW) := troubleMaker && rawNack","val shouldWriteback ="]),
        ("mem/pipeline/NewLoadUnit.scala",1596,1613,["lqWrite.alignedType := in.size","lqWrite.updateAddrValid := ldoutValid || vldoutValid","lqWrite.rep_info.last_beat := paddr(log2Up(refillBytes))"]),
        ("mem/lsqueue/NewStoreQueue.scala",2149,2149,["io.sqEmpty         := virtualStoreQueue.io.empty && physicalQueue.io.empty"]),
        ("Parameters.scala",83,85,["CommitWidth: Int = 8"]),
        ("backend/rob/RobDeqPtrWrapper.scala",59,96,["val deqPosition =","val commitDeqPtrAll =","val deqPtrVec_next ="]),
        ("backend/rob/Rob.scala",1248,1258,["pendingPtrReg := pendingPtrInput","io.lsq.pendingPtr :=","io.lsq.pendingPtrNext := RegNext(deqPtrVec_next.head)"]),
    ):ranges.append(evidence(*source(path),start,end,required))
    return dict(ranges=ranges,maximum_declared_ROB_items=58,unexecuted_STA_peak=1,
        fixed4B_instruction_FTQ_projection=True,first56_S3_complete_but_not_architectural_commit=True,
        overflow_RAW_nack_C_RAW_and_S3_update0=True,full_upstream_native_LDU_Cache_TLB_ROB_proven=False)


def target_points(dat,dut):
    points=[p for p in records(dat) if p['t']=='toggle' and p['f']==str(ROOT/'rtl'/dut/'LoadQueueRAW.sv')]
    stored=[p for p in points if re.fullmatch(r'uop_\d+_debugInfo_runahead_checkpoint_id\[\d+\]:(0->1|1->0)',p['o'])]
    output=[p for p in points if re.fullmatch(r'io_rollback_[01]_bits_debug_runahead_checkpoint_id\[\d+\]:(0->1|1->0)',p['o'])]
    assert len(stored)==7168 and len(output)==256
    rows=[]
    for index in range(56):
        selected=[p for p in stored if p['o'].startswith(f'uop_{index}_debugInfo_')]
        assert len(selected)==128
        rows.append(dict(physical_entry=index,source=str(Path(selected[0]['f']).relative_to(ROOT)),
            source_lines=sorted({int(p['l']) for p in selected}),hit=sum(p['hit']>0 for p in selected),total=128))
    return dict(stored=dict(hit=sum(p['hit']>0 for p in stored),total=7168,by_entry=rows),
        rollback_output=dict(hit=sum(p['hit']>0 for p in output),total=256),
        source_scope=f'rtl/{dut}/LoadQueueRAW.sv',startup_random_values_not_used_to_define_expected_payload=True)


def witnesses(run,dut,*,all_targets=True):
    paths=[p for p in (ROOT/'results'/run/'cases').rglob('load-raw-owner-witness.json') if load(p)['dut']==dut]
    result={}
    for path in paths:
        item=load(path);target=item['target']
        assert target not in result and item['passed'] and item['error'] is None and len(item['rows'])==4
        assert item['local_Load_completions']==4*(56+57-target)
        assert item['actual_Store_Sbuffer_fires']==item['actual_Store_dequeues']==(4 if dut=='lsq_wrapper' else 0)
        previous=set();last_head=0
        for phase,row in enumerate(item['rows']):
            assert row['phase']==phase and row['target']==target
            original=row['original_UIDs'];new=row['refetched_UIDs']
            assert len(original)==57 and len(set(original))==57 and len(new)==57-target
            assert min(new)>max(original) and not previous&set(original+new)
            previous.update(original+new)
            assert row['original_target_UID']==original[target] and row['original_overflow_UID']==original[-1]
            assert row['original_RAW_accepted_UIDs']==original[:56]
            assert row['actual_original_RAW_handshakes']==56 and row['actual_capacity_nacks']==1
            value=((target+1)*0x9E3779B97F4A7C15 ^ 0xA536D240B17E908F)&ALL
            expected=(0,ALL,value,value^ALL)[phase]
            assert row['original_checkpoint']==expected
            rollback=row['rollback'];actual=rollback['actual_fields']
            assert rollback['original_UID']==original[target] and rollback['store_lane']==target%2
            assert rollback['actual_tick']==row['actual_STA_tick']+4
            assert actual['bits_debug_runahead_checkpoint_id']==expected
            rob=phase*58+target+1
            assert actual['bits_robIdx_value']==rob%160 and actual['bits_robIdx_flag']==rob//160%2 and actual['bits_robIdx_isFormer']==1
            assert actual['bits_ftqIdx_value']==rob//4%64 and actual['bits_ftqIdx_flag']==rob//256%2
            assert actual['bits_ftqOffset']==2*(rob%4) and actual['bits_isRVC']==0
            recovery=row['recovery']
            assert recovery['cancelled_UIDs']==original[target:]
            assert recovery['locally_completed_then_ROB_cancelled']==original[target:56]
            assert recovery['active_uncompleted_cancelled']==[original[-1]]
            assert row['original_overflow_position']==row['original_target_position']-target+56
            assert recovery['actual_LQ_tail']==row['original_overflow_position']%240
            assert row['refetch_first_position']==row['original_overflow_position'] and row['refetch_first_UID']==new[0]
            assert row['actual_final_LQ_head']==last_head+56+57-target
            last_head=row['actual_final_LQ_head']
            assert row['max_ROB_program_items']==58 and row['unexecuted_STA_peak']==1 and row['reset_shortcuts']==0
            commit=row['source_projected_ROB_commit_pairs']
            assert commit and commit[0][1]==phase*58 and commit[-1][1]==commit[-1][2]==(phase+1)*58
            assert row['actual_final_ROB_pending']==(phase+1)*58
            for i,(tick,pending,next_pending) in enumerate(commit):
                assert 0<=next_pending-pending<=8 and pending%8+next_pending-pending<=8
                if i:assert pending==commit[i-1][2] and tick==commit[i-1][0]+2
            if dut=='lsq_wrapper':
                assert recovery['actual_SQ_tail']==phase+1 and row['actual_sbuffer_fires']==phase+1
                assert row['original_Store_Sbuffer_completed'] and row['original_Store_bytes_forwarded_to_new_target']
        assert item['last_public_terminal']['LQ_empty'] and item['last_public_terminal']['LQ_head']==last_head
        if dut=='lsq_wrapper':assert item['last_public_terminal']['SQ_empty']
        result[target]=dict(path=str(path.relative_to(ROOT)),SHA256=sha256_file(path),witness=item)
    if all_targets:assert set(result)==set(range(56))
    return result


def calibration():
    a,_=stable_run('load-raw-owners-probe-01');b,_=stable_run('load-raw-owners-probe-02')
    assert a['manifest_tests']=={'PASS':2,'FAIL':2} and b['manifest_tests']=={'PASS':4}
    first=cases(a['run']);second=cases(b['run']);assert set(first)==set(second)
    assert all('self.fires==self.dequeues==self.sq+1' in row['detail'] for row in first.values() if row['outcome']=='FAIL')
    for path in (ROOT/'results'/a['run']/'cases').rglob('load-raw-owner-witness.json'):
        item=load(path)
        if item['dut']=='lsq_wrapper':assert not item['passed'] and item['actual_Store_Sbuffer_fires']==item['actual_Store_dequeues']==1
    protocol,_=stable_run('load-raw-owners-probe-03')
    assert protocol['manifest_tests']=={'PASS':4}
    for dut in FILES:assert set(witnesses('load-raw-owners-probe-03',dut,all_targets=False))=={0,55}
    correction_path=ROOT/'results/lsq-RAW-owners-after-01/ROB-source-correction-v1.json'
    correction=load(correction_path)
    assert correction['old_bytes_reconstructed_and_verified_against_original_full_library_aggregate']
    assert correction['new_producer_SHA256']==sha256_file(ROOT/'lsqverify/load_raw_owners.py')
    for name in ('lq-RAW-owners-after-01','lsq-RAW-owners-after-01'):
        historical=load(ROOT/'results'/name/'load-RAW-owners-evidence-v1.json')
        assert not historical['normal_ROB_admission']['proven']
    limitation=load(ROOT/'results/load-raw-owners-contributor-regression-01/runner-limitation-v1.json')
    assert limitation['exitstatus']==2 and not limitation['native_DUT_execution_started']
    return dict(first_probe=a,corrected_probe=b,original_two_failure_SHA256=failure_digest(first),
        changed='Wait until both actual SQ deq and actual combined SQ-empty; old demand on the same deq edge was too early. Both checks remain. Original two failures stay unedited.',
        later_formal_payload_control='STA lane fixed target%2 across all4known payload writes, avoiding reliance on startup random directions.',
        later_pending_protocol_correction='The first formal01profiles jumped pending58entries at program end. Their LSQ results remain valid interface evidence, not a normal ROB commit history. Formal02checks CommitWidth8 line boundary and pending follows the previous pendingNext sample.',
        corrected_protocol_probe=protocol,producer_correction_evidence=str(correction_path.relative_to(ROOT)),
        producer_correction_SHA256=sha256_file(correction_path),runner_scheduling_limit=limitation,
        no_saved_cycle_prefix_replay_claimed=True)


def audit_pair(dut,before,after):
    a,b=validate_run(before,dut),validate_run(after,dut)
    assert a['source']==b['source']
    old,new=cases(before),cases(after);added=set(new)-set(old)
    assert len(added)==56 and all(new[node]==value for node,value in old.items())
    assert all(node.startswith(FILES[dut][:-3].replace('/','.')+'::') and new[node]['outcome']=='PASS' for node in added)
    summary_before,summary_after=node_summaries(before,dut+'.summary.json'),node_summaries(after,dut+'.summary.json')
    assert all(summary_after[node]==value for node,value in summary_before.items())
    closure=delta(before,after,dut,dut.upper()+'-RAW-ORIGINAL-OWNERS',FILES[dut]+'::target[0..55]')
    assert all(closure['verification'].values())
    targets=dict(before=target_points(a['dat'],dut),after=target_points(b['dat'],dut))
    assert targets['after']['stored']['hit']==7168 and targets['after']['rollback_output']['hit']==256
    ws=witnesses(after,dut)
    report=dict(format='lsq-load-RAW-owners-evidence-v1',dut=dut,before_run=before,after_run=after,
        contract='docs/contracts/load-raw-checkpoint-owners.md',source_aggregate=a['source']['aggregate_SHA256'],
        baseline_tests=len(old),after_tests=len(new),added_nodes=sorted(added),
        native_build_id=closure['native_build_id'],raw_nonwrapper_metrics=closure['metrics'],targets=targets,
        original_source_line_coverage=line_delta(source_lines(a['meta'],a['dat'],dut),source_lines(b['meta'],b['dat'],dut)),
        witness_files=[dict(target=t,path=v['path'],SHA256=v['SHA256']) for t,v in sorted(ws.items())],
        public_lifetimes=dict(targets=56,profiles_per_target=4,original_RAW_handshakes=56*56*4,
            capacity_nacks=56*4,original_checkpoint_rollbacks=56*4,original_Store_completions=56*4 if dut=='lsq_wrapper' else None,
            source_projected_max_ROB_items=58,unexecuted_STA_peak=1,reset_shortcuts=0),
        producer_source=pinned_source(),calibration=calibration(),
        verification=dict(actual_real_parent_and_full_reference=True,same_source_build_and_all3point_sets=True,
            old_results_and_primary_streams_preserved=True,all56original_target_UIDs_checked_in4profiles=True,
            real57th_RAW_nack_and_source_S3=True,original_rollback_fields_and_exact_timing_checked=True,
            actual_redirect_and_new_UID_same_cancelled_LQ_position=True,original_Store_shared_STA_survives_and_completes=True,
            all7168registered_and256rollback_directions_hit=True,no_old_native_hit_lost=True,
            local_release_not_promoted_to_architectural_commit=True,no_midprogram_reset_or_private_stimulus=True),
        limits='Aligned normal boundary-source projection, not native full-core/Cache/LDU/TLB/ROB validation. Isolated LQ has external SQ readiness and no StoreQueue/Forward result. Old unit-interface raw-probe tests,192FAILs and other remaining domains are not replaced or waived.')
    write_report(ROOT/'results'/after/'load-RAW-owners-evidence-v1.json',report)
    return report


def prior_source_unchanged():
    previous=load(ROOT/'results'/BEFORE_FULL/'source-aggregate-launch.json')
    extra={'lsqverify':{'lsqverify/runtime_profile.py','lsqverify/codec_cache.py','lsqverify/load_raw_owners.py'},
        'tests':{'tests/runtime/test_codec_cache.py',*FILES.values()}}
    rows={}
    for group,excluded in extra.items():
        pairs=[]
        for path in (ROOT/group).rglob('*'):
            name=str(path.relative_to(ROOT))
            if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc' or name in excluded:continue
            pairs.append((name,sha256_file(path)))
        result=aggregate(pairs)
        assert result==previous['groups'][group]
        rows[group]=dict(original_aggregate=result,added_files={name:sha256_file(ROOT/name) for name in sorted(excluded)})
    return dict(groups=rows,all159prior_library_and195test_files_unchanged=True,
        scope='The old actual8build baseline is reused without another full DUT run. Its complete original verification-library/tests aggregates are exactly recovered after excluding explicitly listed new files. New source additions remain recorded, not claimed globally identical to the641file historical source set.')


def audit_full():
    status,source_set=stable_run(FULL);previous_status,_=stable_run(BEFORE_FULL)
    old,new=cases(BEFORE_FULL),cases(FULL)
    assert len(old)==1457 and len(new)==1569 and all(new[node]==value for node,value in old.items())
    added=set(new)-set(old)
    assert added==set().union(*(set(cases(after))-set(cases(before)) for _,before,after in PAIRS))
    assert len(added)==112 and all(new[node]['outcome']=='PASS' for node in added)
    assert status['manifest_tests']=={'PASS':1377,'FAIL':192} and status['pytest_exitstatus']==1
    assert failure_digest(old)==failure_digest(new)
    command=load(ROOT/'results'/FULL/'command.json')['command']
    assert command[command.index('--lsq-trace-max-mb')+2:]==FULL_PATHS+['--tb=short']
    assert '--lsq-codec-cache' not in command and '-p' not in command
    a,b=contributors(BEFORE_FULL),contributors(FULL)
    for dut,items in a.items():assert all(same_summary(value,b[dut][node]) for node,value in items.items())
    assert len(b['lsq_wrapper'])==len(a['lsq_wrapper'])+56==801
    old_streams,new_streams=journal_streams(BEFORE_FULL),journal_streams(FULL)
    assert len(old_streams)==2235 and len(new_streams)==2403
    assert all(new_streams[key]==value for key,value in old_streams.items())
    all_nodes=set().union(*(set(items) for items in b.values()))
    for dut in ('load_queue','load_queue_uncache','virtual_store_queue','unalign_queue'):
        before=node_summaries(BEFORE_FULL,dut+'.summary.json');after=node_summaries(FULL,dut+'.summary.json')
        assert all(after[node]==value for node,value in before.items()) and len(after)==len(before)+int(dut=='load_queue')*56
        meta,_=native(FULL,dut);assert meta['artifact']['input_files']==len(after)
        all_nodes|={xml_node(node) for node in after}
    assert all_nodes==set(new)
    rows=[]
    for dut in ('forward_module','physical_store_queue','store_queue','lsq_wrapper','unalign_queue','virtual_store_queue','load_queue_uncache','load_queue'):
        ma,da=native(BEFORE_FULL,dut);mb,db=native(FULL,dut)
        assert ma['artifact']['build']==mb['artifact']['build']
        parsed=summarize(db,mb['artifact']['build'],mb['artifact'])
        assert parsed['raw_parser_matches_analyzer'] and parsed['coverage_artifact_matches_dat']
        for path,digest in mb['artifact']['build']['files'].items():assert sha256_file(Path(path))==digest
        a,b=point_sets(da),point_sets(db);metrics={}
        for kind in a:
            assert a[kind]['all']==b[kind]['all'] and a[kind]['hit']<=b[kind]['hit']
            metrics[kind]=dict(before_hit=len(a[kind]['hit']),after_hit=len(b[kind]['hit']),total=len(b[kind]['all']),
                newly_hit=len(b[kind]['hit']-a[kind]['hit']),newly_hit_SHA256=digest_keys(b[kind]['hit']-a[kind]['hit']),
                newly_missing=0,still_missing=len(b[kind]['missing']),still_missing_SHA256=digest_keys(b[kind]['missing']))
        row=dict(dut=dut,metrics=metrics,before_coverage_dat_SHA256=sha256_file(da),after_coverage_dat_SHA256=sha256_file(db),
            original_native_inputs=ma['artifact']['input_files'],current_native_inputs=mb['artifact']['input_files'],
            original_source_line_coverage=line_delta(source_lines(ma,da,dut),source_lines(mb,db,dut)))
        if dut in FILES:
            directed=next(after for key,_,after in PAIRS if key==dut)
            x,y=witnesses(FULL,dut),witnesses(directed,dut)
            assert {t:v['witness'] for t,v in x.items()}=={t:v['witness'] for t,v in y.items()}
            row['targets']=dict(before=target_points(da,dut),after=target_points(db,dut))
            assert row['targets']['after']['stored']['hit']==7168 and row['targets']['after']['rollback_output']['hit']==256
        else:assert sha256_file(da)==sha256_file(db)
        rows.append(row)
    prior=load(ROOT/'results'/BEFORE_FULL/'load-response-payload-contributor-evidence-v1.json')
    assert all(sha256_file(ROOT/path)==digest for path,digest in prior['unchanged_generic_actor_SHA256'].items())
    report=dict(format='lsq-load-RAW-owners-contributor-v1',run=FULL,baseline_run=BEFORE_FULL,status=status,
        baseline_status=previous_status,source_aggregate=source_set['aggregate_SHA256'],prior_source_evidence=prior_source_unchanged(),
        original_nodes=1457,current_nodes=1569,added_passing_nodes=112,original_failures=192,
        original_failure_SHA256=failure_digest(old),current_failure_SHA256=failure_digest(new),rows=rows,
        required_new_functional_failures=prior['required_new_functional_failures'],
        prior_domain_limited_evidence=prior['prior_domain_limited_evidence'],calibration=calibration(),
        coverage_monotonicity=dict(name='all_old_native_hits_retained',passed=True,status='PASS',failed_duts=[],newly_missing_toggle_points=0,required=True,waived=False),
        verification=dict(actual_fresh_complete_eight_build_after=True,original1457_results_and192FAIL_details_equal=True,
            all_prior_library_tests_unchanged_except_listed_additions=True,all_native_contributors_and_old_streams_preserved=True,
            same_builds_and_all3point_universes=True,no_old_native_hit_lost=True,all112witnesses_equal_directed=True,
            all56targets_and4normal_source_profiles_checked=True,prior_required_failure_and_domain_limits_kept=True,
            no_full_baseline_DUT_rerun_or_coverage_OR=True,all_native_hashes_and_locked_analyzer_checked=True),
        limits='Normal aligned LSQ boundary producer evidence only, not native upstream/full38DUT acceptance. Latest independent run is not a rewrite of2330node regression15 or its227FAIL inventory. Existing original failures and broader recovery/disabled/SID/cross-page domains remain.')
    write_report(ROOT/'results'/FULL/'load-RAW-owners-contributor-evidence-v1.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--full',action='store_true');args=parser.parse_args()
    for pair in PAIRS:
        row=audit_pair(*pair);print(json.dumps({key:row[key] for key in ('dut','baseline_tests','after_tests','raw_nonwrapper_metrics','verification')},indent=2))
    if args.full:print(json.dumps(audit_full(),indent=2))
