#!/usr/bin/env python3
"""Audit opt-in pure-adapter controls, never claim native coverage gains."""
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

from audit_coverage_points_v1 import sha256_file,summarize
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases,failure_digest
from audit_gap_closure_v1 import native
from audit_load_response_payload_v1 import FULL
from audit_native_case_probe_v1 import journal_streams,stable_run

ROOT=Path(__file__).resolve().parents[1]
CONTROLS=(("lsq-codec-cache-baseline-01",False),("lsq-codec-cache-after-01",True),
          ("lsq-codec-cache-after-02",True),("lsq-codec-cache-baseline-02",False))


def load(path):return json.loads(path.read_text())


def durations(name):
    return {t.attrib["classname"]+"::"+t.attrib["name"]:float(t.attrib["time"])
            for t in ET.parse(ROOT/"results"/name/"pytest.xml").getroot().iter("testcase")}


def audit():
    unit,unit_source=stable_run("lsq-codec-cache-unit-01")
    assert unit["total_cases"]==6 and unit["manifest_tests"]=={"PASS":6}
    first=CONTROLS[0][0];expected=cases(first);streams=journal_streams(first)
    assert len(expected)==6 and len(streams)==18
    original=cases(FULL);original_streams=journal_streams(FULL)
    assert all(original[node]==value for node,value in expected.items())
    assert all(original_streams[key]==value for key,value in streams.items())
    profile="lsq-runtime-profile-01";profile_status,_=stable_run(profile)
    assert profile_status["manifest_tests"]=={"PASS":1,"FAIL":1}
    assert all(expected[node]==value for node,value in cases(profile).items())
    assert all(streams[key]==value for key,value in journal_streams(profile).items())
    first_meta,first_dat=native(first,"lsq_wrapper")
    analyzer=summarize(first_dat,first_meta["artifact"]["build"],first_meta["artifact"])
    assert analyzer["raw_parser_matches_analyzer"] and analyzer["coverage_artifact_matches_dat"]
    build=first_meta["artifact"]["build"]
    for path,digest in build["files"].items():assert sha256_file(Path(path))==digest
    source=None;rows=[];summaries={}
    for name,enabled in CONTROLS:
        status,current=stable_run(name)
        if source is None:source=current
        assert current==source==unit_source
        assert cases(name)==expected and journal_streams(name)==streams
        assert status["manifest_tests"]=={"PASS":5,"FAIL":1} and status["pytest_exitstatus"]==1
        meta,dat=native(name,"lsq_wrapper")
        assert meta["artifact"]["build"]==build and meta["artifact"]["input_files"]==6
        assert sha256_file(dat)==sha256_file(first_dat)
        command=load(ROOT/"results"/name/"command.json")["command"]
        assert ("--lsq-codec-cache" in command)==enabled and "--lsq-runtime-profile" not in command
        paths=sorted((ROOT/"results"/name/"cases").rglob("codec-cache-summary.json"))
        assert len(paths)==(6 if enabled else 0)
        by_node={}
        for path in paths:
            item=load(path)
            assert item["restored_all_aliases"] and item["implementation_SHA256"]==sha256_file(ROOT/"lsqverify/codec_cache.py")
            assert len(item["rows"])==4
            assert all(row["hits"]>0 and row["misses"]>0 and row["retained_values"]<=row["capacity"]==64 for row in item["rows"])
            by_node[item["nodeid"]]=item
        if enabled:summaries[name]=by_node
        timing=durations(name)
        rows.append(dict(run=name,enabled=enabled,status=status,case_seconds=timing,
            case_total_seconds=sum(timing.values()),all18_primary_streams_equal=True,
            all6_outcomes_and_original_strict_failure_detail_equal=True,
            native_dat_SHA256=sha256_file(dat),all_native_point_keys_and_counter_values_byte_equal=True,
            cache_summaries=[dict(path=str(path.relative_to(ROOT)),SHA256=sha256_file(path)) for path in paths]))
    assert summaries["lsq-codec-cache-after-01"]==summaries["lsq-codec-cache-after-02"]
    before=statistics.mean(row["case_total_seconds"] for row in rows if not row["enabled"])
    after=statistics.mean(row["case_total_seconds"] for row in rows if row["enabled"])
    timing_path=ROOT/"results/lsq-codec-cache-after-02/runtime-timing-receipt-v1.json"
    timing=load(timing_path)
    raw_tool_log=Path(timing["source_tool_log"])
    assert sha256_file(raw_tool_log)==timing["source_tool_log_SHA256"]
    raw_text=raw_tool_log.read_text()
    assert timing["measurements"]==json.loads(raw_text[raw_text.rfind("\n[")+1:])
    observed=timing["measurements"]
    assert [(row["run"],row["cache_enabled"]) for row in observed]==list(CONTROLS)
    assert all(row["status"]==1 and row["whole_runner_seconds"]>0 for row in observed)
    elapsed={row["run"]:row["whole_runner_seconds"] for row in observed}
    baseline_elapsed=statistics.mean(row["whole_runner_seconds"] for row in observed if not row["cache_enabled"])
    after_elapsed=statistics.mean(row["whole_runner_seconds"] for row in observed if row["cache_enabled"])
    prior=load(ROOT/"results"/FULL/"load-response-payload-contributor-evidence-v1.json")
    frozen=prior["unchanged_generic_actor_SHA256"]
    assert all(sha256_file(ROOT/path)==digest for path,digest in frozen.items())
    report=dict(format="lsq-runtime-performance-control-v1",contract="docs/contracts/lsq-runtime-summary-performance.md",
        source_aggregate=source["aggregate_SHA256"],unit_tests=unit,profile_status=profile_status,rows=rows,
        measurement=dict(order=[name for name,_ in CONTROLS],profile_enabled=False,
            average_baseline_testcase_seconds=before,average_cached_testcase_seconds=after,
            testcase_time_reduction_fraction=1-after/before,
            timing_scope="JUnit testcase time includes fixture setup/call/teardown; not an isolated call-time or whole-run guarantee",
            whole_runner_seconds_observed=elapsed,timing_receipt=str(timing_path.relative_to(ROOT)),
            timing_receipt_SHA256=sha256_file(timing_path),
            whole_runner_time_reduction_fraction=1-after_elapsed/baseline_elapsed),
        actual_original_failure_SHA256=failure_digest(expected),unchanged_frozen_source_SHA256s=frozen,
        original192_failure_list_replaced=False,default_enabled=False,whole38DUT_or1457_speed_guarantee=False,
        native_coverage_gain=0,verification=dict(actual_real_DUT_positive_and_required_failure_controls=True,
            NC_MMIO_errors_and_S4_fault_recovery_controls=True,same_all6_cases_and_original_strict_failure=True,
            same_source_build_and18_public_check_actor_streams=True,all_native_bytes_and_counters_equal=True,
            pure_frozen_input_only_and_fresh_return_containers_unit_checked=True,
            bounded64_per_encoder_per_case_and_restored_aliases=True,frozen_reference_actor_sources_unchanged=True,
            no_DUT_or_model_state_caching=True,no_cycle_trace_or_waveforms=True,
            summary_format_bytes_not_changed=True,not_default_or_full_scope_acceptance=True),
        limits="Six real Wrapper controls plus6pure unit tests, not every LSQ/native configuration or full long-case benchmark. Marginal measured gains do not justify promising proportional speed for37.9minutes. Mixed5000cycle failures remain and no wait budget/check is reduced. Pure encoder validations run on cache misses; equal immutable inputs reuse the same validated pin map, never model outputs or expected-value comparisons.")
    write_report(ROOT/"results/lsq-codec-cache-after-02/runtime-performance-control-v1.json",report)
    return report


if __name__=="__main__":
    result=audit()
    print(json.dumps({key:result[key] for key in ("measurement","verification","default_enabled","native_coverage_gain")},indent=2))
