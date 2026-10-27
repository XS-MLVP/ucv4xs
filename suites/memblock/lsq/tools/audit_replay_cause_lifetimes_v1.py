#!/usr/bin/env python3
"""Audit original-UID repeated Replay lifetimes and actual coverage sets."""
from collections import Counter
import json
from pathlib import Path
import re

from audit_checkpoint_pool_v1 import validate_run
from audit_coverage_points_v1 import records, sha256_file, summarize
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases, failure_digest
from audit_gap_closure_v1 import audit as gap_delta, native, point_sets, point_key, digest_keys
from audit_native_case_probe_v1 import stable_run, journal_streams, xml_node
from audit_native_contributor_scope_v1 import contributors, same_summary
from audit_normal_replay_metadata_v1 import FULL as BASE, FULL_PATHS, target_summary
from audit_sq_head_permit_domain_v1 import source, evidence
from audit_store_strict_lifetimes_v1 import source_lines
from audit_uq_page_pairs_v1 import node_summaries
from audit_vsq_release_windows_v1 import line_delta
from run_summary import aggregate

ROOT = Path(__file__).resolve().parents[1]
FULL = "replay-cause-lifetimes-contributor-regression-03"
PAIRS = (("load_queue_replay", "lrq-cause-lifetimes-before-03", "lrq-cause-lifetimes-after-03"),
    ("load_queue", "lq-cause-lifetimes-before-03", "lq-cause-lifetimes-after-03"),
    ("lsq_wrapper", "lsq-cause-lifetimes-before-03", "lsq-cause-lifetimes-after-03"))
NEW = {dut: f"tests/{folder}/test_cause_lifetimes.py" for dut, folder in
    (("load_queue_replay", "replay"), ("load_queue", "load_queue"), ("lsq_wrapper", "lsq_wrapper"))}
OLD = {dut: f"tests/{folder}/{file}.py" for dut, folder, file in
    (("load_queue_replay", "replay", "test_normal_metadata"),
     ("load_queue", "load_queue", "test_normal_replay_metadata"),
     ("lsq_wrapper", "lsq_wrapper", "test_normal_replay_metadata"))}


def load(path):
    return json.loads(path.read_text())


def calibration():
    path = ROOT / 'results/replay-cause-lifetimes-contributor-regression-01/PA-lastBeat-source-correction-v1.json'
    report = load(path)
    width_path = ROOT / 'results/replay-cause-lifetimes-contributor-regression-02/refill-width-source-correction-v2.json'
    width = load(width_path)
    from audit_refill_width_source_projection_v1 import source_chain
    assert width['parameter_chain'] == source_chain() and width['parameter_chain']['address_bit'] == 5
    v3_path = width_path.with_name('PA-bit5-producer-correction-v3.json')
    v3 = load(v3_path)
    assert v3['corrected_producer_SHA256'] == sha256_file(ROOT / 'lsqverify/replay_cause_lifetimes.py')
    assert v3['old02producer_bytes_and_entire_library_aggregate_verified']
    assert report['old_helper_bytes_and_entire_library_and_test_aggregates_verified']
    assert report['first_post_audit_actual_exitstatus'] == 1
    assert sha256_file(ROOT / report['first_post_audit_failure_log']) == report['first_post_audit_failure_log_SHA256']
    assert sha256_file(ROOT / report['first_post_audit_receipt']) == report['first_post_audit_receipt_SHA256']
    historical = []
    for dut, prefix in (('load_queue_replay', 'lrq'), ('load_queue', 'lq'), ('lsq_wrapper', 'lsq')):
        evidence_path = ROOT / 'results' / f'{prefix}-cause-lifetimes-after-01/Replay-cause-lifetime-evidence-v1.json'
        old = load(evidence_path)
        assert not old['PA_lastBeat_source_admission']['proven']
        historical.append(dict(dut=dut, evidence=str(evidence_path.relative_to(ROOT)), SHA256=sha256_file(evidence_path),
            domain=old['PA_lastBeat_source_admission']['domain']))
        second_path = ROOT / 'results' / f'{prefix}-cause-lifetimes-after-02/Replay-cause-lifetime-evidence-v1.json'
        second = load(second_path)
        assert not second['fixed_refill_width_source_admission']['proven']
        historical.append(dict(dut=dut, evidence=str(second_path.relative_to(ROOT)), SHA256=sha256_file(second_path),
            domain=second['fixed_refill_width_source_admission']['domain']))
    return dict(source_correction=str(path.relative_to(ROOT)), source_correction_SHA256=sha256_file(path),
        historical_interface_runs=historical, first_post_audit_failure_log=report['first_post_audit_failure_log'],
        first_post_audit_failure_log_SHA256=report['first_post_audit_failure_log_SHA256'],
        original01_and02raw_results_and_failures_retained=True,
        refill_width_source_correction=str(width_path.relative_to(ROOT)), refill_width_source_correction_SHA256=sha256_file(width_path),
        bit5_producer_correction=str(v3_path.relative_to(ROOT)), bit5_producer_correction_SHA256=sha256_file(v3_path),
        formal03_checks_PA_and_every_S3_lastBeat_against_fixed32B_refill=True,
        probe03_eight_UIDs_cover_both_PA_bit5_values=True, old1762baseline_reexecuted=False)


def old_sources():
    prior = load(ROOT / "results" / BASE / "source-aggregate-launch.json")
    excludes = {"lsqverify": {"lsqverify/replay_cause_lifetimes.py"},
        "tests": {*NEW.values(), "tests/replay_cause_probe/test_probe.py"}}
    result = {}
    for group, names in excludes.items():
        rows = [(str(p.relative_to(ROOT)), sha256_file(p)) for p in (ROOT / group).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc" and str(p.relative_to(ROOT)) not in names]
        original = aggregate(rows)
        assert original == prior["groups"][group]
        result[group] = dict(original=original, excluded_new_files={name: sha256_file(ROOT / name) for name in sorted(names)})
    for group in ("pytest.ini", "README.md", "manifest"):
        paths = [ROOT / group] if group != "manifest" else [p for p in (ROOT / group).rglob("*") if p.is_file()]
        fingerprint = aggregate([(str(p.relative_to(ROOT)), sha256_file(p)) for p in paths])
        assert fingerprint == prior["groups"][group]
        result[group] = fingerprint
    return dict(verified=True, groups=result, old_models_actors_helpers_and_tests_unchanged=True)


def source_projection():
    ranges = []
    for path, start, end, checks in (
        ("mem/pipeline/NewLoadUnit.scala", 1111, 1127, ["cause(C_DR) := troubleMaker && needDCacheAccess && mshrNack", "cause(C_DM) := troubleMaker && needDCacheAccess && dcacheMiss", "cause(C_WF) := false.B", "cause(C_MF) := false.B"]),
        ("mem/pipeline/NewLoadUnit.scala", 1464, 1488, ["val doFastReplay = shouldFastReplay && allowFastReplay", "val s3RevokeReplay = causeOrR"]),
        ("mem/pipeline/NewLoadUnit.scala", 1557, 1569, ["!doFastReplay", "val lqWriteCauseOH = PriorityEncoderOH(lqWriteCause)"]),
        ("mem/pipeline/NewLoadUnit.scala", 1602, 1618, ["lqWrite.schedIndex := in.replayQueueIdx.get", "lqWrite.updateAddrValid := ldoutValid || vldoutValid", "lqWrite.rep_info.last_beat := paddr(log2Up(refillBytes))", "lqWrite.rep_info.cause := lqWriteCauseOH"]),
        ("mem/lsqueue/LoadQueueReplay.scala", 868, 912, ["scheduled(enqIndex) := false.B", "cause(enqIndex) := replayInfo.cause.asUInt", "blocking(enqIndex) := false.B"]),
        ("mem/lsqueue/LoadQueueReplay.scala", 957, 973, ["when(enq.bits.handledByMSHR)", "missMSHRId(enqIndex) := replayInfo.mshr_id", "when (enq.valid && enq.bits.isLoadReplay)"]),
    ):
        ranges.append(evidence(*source(path), start, end, checks))
    return dict(ranges=ranges, native_upstream_pipeline_or_allocator_proven=False,
        fast_path_declined_not_native_fast_path_validated=True, all_four_causes_have_fixed_source_projection=True)


def targets(dat, dut):
    path = ROOT / "dut/load_queue_replay/LoadQueueReplayDut.v" if dut == "load_queue_replay" else ROOT / "rtl" / dut / "LoadQueueReplay.sv"
    ps = [p for p in records(dat) if p["f"] == str(path) and p["t"] == "toggle" and re.fullmatch(r"cause_\d+\[\d+\]:(0->1|1->0)", p["o"])]
    assert len(ps) == 3120
    selected = [p for p in ps if int(re.search(r"\[(\d+)\]", p["o"])[1]) in (3, 5, 6, 8)]
    assert len(selected) == 960
    ids = target_summary(dat, dut)
    return dict(all_cause_hit=sum(p["hit"] > 0 for p in ps), all_cause_total=3120,
        known_cause_bits=[3, 5, 6, 8], known_cause_target_hit=sum(p["hit"] > 0 for p in selected), known_cause_target_total=960,
        missing_cause_target_SHA256=digest_keys({point_key(p) for p in selected if not p["hit"]}),
        IDs={key: ids[key] for key in ("MSHR_id", "TLB_hint_id")})


def witness(run, dut, count=120):
    paths = [p for p in (ROOT / "results" / run / "cases").rglob("replay-cause-lifetime-witness.json") if load(p)["dut"] == dut]
    assert len(paths) == 1
    path = paths[0]
    r = load(path)
    assert r["passed"] and r["error"] is None and r["count"] == r["completed"] == len(r["rows"]) == count
    assert r["actual_grants"] == r["actual_feedbacks"] == count * 9
    assert not r["reset_between_owners"] and r["peak_live_Loads"] == 1 and not r["native_upstream_allocator_proven"]
    seq, mshr, dependency = (3, 6, 5, 8, 3, 5, 6, 3, 8), (0, 15, 15, 15, 15, 15, 0, 0, 0), (0, 15, None, None, 15, None, 0, 0, None)
    slots = []
    for index, row in enumerate(r["rows"]):
        assert row["uid"] == index + 1 and row["ROB_ordinal"] == row["LQ_position"] == index
        assert row["operation"] == 6 and row["vaddr"] == 0x10000 + 16 * index + 8 and row["mask"] == 0xFF00
        assert row["PA"] == 0x80000000 + index * 4096 + row["vaddr"] % 4096
        assert row["initial_S3_last_beat"] == bool(row["PA"] & 32)
        assert row["FTQ_value"] == index // 16 and row["FTQ_end_offset"] == 2 * (index % 16) + 1
        assert row["checkpoint"] == ((index + 1) * 0x9E3779B97F4A7C15) % (1 << 64)
        assert len(row["grants"]) == 9 and row["original_UID_completion"]
        slots.append(row["public_slot"])
        for phase, item in enumerate(row["grants"]):
            assert item["cause_index"] == phase and item["cause"] == seq[phase]
            assert item["public_slot"] == row["public_slot"] and item["bank"] == row["public_slot"] % 3
            assert item["expected_MSHR_ID"] == mshr[phase] and item["dependency_ID"] == dependency[phase]
            assert item["hold_cycles"] == 3 and item["grant_tick"] == item["first_offer_tick"] + 8
            assert item["feedback_tick"] == item["grant_tick"] + 6
            assert item["feedback_last_beat"] == bool(row["PA"] & 32)
            assert item["feedback_need_replay"] == (phase != 8) and item["feedback_updateAddrValid"] == (phase == 8)
            assert item["next_cause"] == (seq[phase + 1] if phase < 8 else None)
            assert item["feedback_handledByMSHR"] == (phase + 1 in (1, 6))
            assert item["retained_MSHR_ID_after_feedback"] == (mshr[phase + 1] if phase < 8 else 0)
            assert item["feedback_MSHR_pin"] == (dependency[phase + 1] if phase + 1 in (1, 6) else 7)
            previous = row["initial_S3_tick"] if phase == 0 else row["grants"][phase - 1]["feedback_tick"]
            assert item["initial_S3_or_previous_feedback_tick"] == previous
            if seq[phase] in (3, 6):
                assert item["wrong_channel_tick"] == previous + 10
                assert item["wrong_ID_tick"] == item["wrong_channel_tick"] + 10
                assert item["matched_tick"] == item["wrong_ID_tick"] + 10
                assert item["first_offer_tick"] == item["matched_tick"] + (0 if seq[phase] == 3 else 4)
            else:
                assert item["first_offer_tick"] == previous + 2
                assert item["wrong_channel_tick"] is item["wrong_ID_tick"] is item["matched_tick"] is None
        assert row["actual_release_tick"] >= row["grants"][-1]["feedback_tick"] + (0 if dut == "load_queue_replay" else 4)
    assert len(set(slots)) == count and (count != 120 or set(slots) == set(range(120)))
    return dict(path=str(path.relative_to(ROOT)), SHA256=sha256_file(path), witness=r)


def audit_pair(dut, before, after):
    a, b = validate_run(before, dut), validate_run(after, dut)
    assert a["source"] == b["source"]
    old, new = cases(before), cases(after)
    assert len(old) == 4 and len(new) == 5 and all(new[node] == value for node, value in old.items())
    added = set(new) - set(old)
    assert len(added) == 1 and next(iter(added)).startswith(NEW[dut][:-3].replace("/", ".") + "::")
    old_j, new_j = node_summaries(before, dut + ".summary.json"), node_summaries(after, dut + ".summary.json")
    assert all(new_j[node] == value for node, value in old_j.items())
    closure = gap_delta(before, after, dut, "REPLAY-CAUSE-ORIGINAL-UID-LIFETIMES", NEW[dut])
    assert all(closure["verification"].values())
    ts = dict(before=targets(a["dat"], dut), after=targets(b["dat"], dut))
    assert ts["after"]["known_cause_target_hit"] == 960
    assert all(v["legal_target_hit"] == v["legal_target_total"] for v in ts["after"]["IDs"].values())
    ws = witness(after, dut)
    probe = witness("replay-cause-lifetimes-probe-03", dut, count=8)
    result = dict(format="lsq-Replay-cause-lifetime-directed-v1", dut=dut, before=before, after=after,
        old_nodes=4, new_nodes=5, contract="docs/contracts/replay-cause-lifetimes.md", metrics=closure["metrics"],
        target_domains=ts, original_source_line_coverage=line_delta(source_lines(a["meta"], a["dat"], dut), source_lines(b["meta"], b["dat"], dut)),
        compact_witness=dict(path=ws["path"], SHA256=ws["SHA256"]), probe=dict(path=probe["path"], SHA256=probe["SHA256"]),
        source_projection=source_projection(), old_sources=old_sources(), calibration=calibration(),
        verification=dict(immutable_original_UID_120actual_public_slots=True, nine_real_grants_eight_rereplays_then_final_feedback=True,
            wrong_active_ID_and_wrong_channel_did_not_unlock=True, exact_timing_hold_MSHR_history_and_final_release_checked=True,
            every_original_and_feedback_S3_lastBeat_equals_fixed32B_PA_bit5=True,
            known_cause_bits_all960directions_hit=True, original_nodes_streams_and_native_hits_kept=True,
            same_source_build_and_all3point_universes=True),
        limits="Directed normal scalar cause lifetime evidence only, not complete9build or whole38DUT acceptance. NC,Store/RAW/RAR/strict/disabled/cancel/vector/exception and all previous boundaries remain.")
    write_report(ROOT / "results" / after / "Replay-cause-lifetime-evidence-v1.json", result)
    return result


def audit_full():
    status, src = stable_run(FULL)
    old, new = cases(BASE), cases(FULL)
    added = set(new) - set(old)
    expected_added = set().union(*(set(cases(after)) - set(cases(before)) for _, before, after in PAIRS))
    assert len(old) == 1762 and len(new) == 1765 and added == expected_added and len(added) == 3
    assert all(new[node]["outcome"] == "PASS" for node in added)
    assert status["manifest_tests"] == {"PASS": 1569, "FAIL": 196}
    assert all(new[node] == value for node, value in old.items()) and failure_digest(old) == failure_digest(new)
    rows = []
    primary_a, primary_b = contributors(BASE), contributors(FULL)
    for dut, values in primary_a.items():
        assert all(same_summary(value, primary_b[dut][node]) for node, value in values.items())
        expected_new = {node for node in added if node.startswith(NEW[dut][:-3].replace("/", ".") + "::")} if dut in NEW else set()
        assert set(primary_b[dut]) == set(values) | expected_new
    all_nodes = set().union(*(set(values) for values in primary_b.values()))
    sa, sb = journal_streams(BASE), journal_streams(FULL)
    assert len(sa) == 2415 and len(sb) == 2418 and all(sb[k] == v for k, v in sa.items())
    command = load(ROOT / "results" / FULL / "command.json")["command"]
    assert command[command.index("--lsq-trace-max-mb") + 2:] == FULL_PATHS + ["--tb=short"]
    manifest = load(ROOT / "results" / FULL / "execution/manifest.json")
    native_artifacts = [artifact for artifact in manifest["artifacts"] if artifact["kind"] == "native"]
    assert len(native_artifacts) == 9 and "--lsq-codec-cache" not in command
    for item in load(ROOT / "results" / BASE / "normal-replay-metadata-contributor-evidence-v1.json")["rows"]:
        dut = item["dut"]
        a, da = native(BASE, dut); b, db = native(FULL, dut)
        assert a["artifact"]["build"] == b["artifact"]["build"]
        for filename, digest in b["artifact"]["build"]["files"].items():
            assert sha256_file(Path(filename)) == digest
        summary = summarize(db, b["artifact"]["build"], b["artifact"])
        assert summary["raw_parser_matches_analyzer"] and summary["coverage_artifact_matches_dat"]
        old_pts, new_pts = point_sets(da), point_sets(db)
        metrics = {}
        for kind in old_pts:
            x, y = old_pts[kind], new_pts[kind]
            assert x["all"] == y["all"] and x["hit"] <= y["hit"]
            metrics[kind] = dict(before_hit=len(x["hit"]), after_hit=len(y["hit"]), total=len(y["all"]),
                newly_hit=len(y["hit"] - x["hit"]), newly_hit_SHA256=digest_keys(y["hit"] - x["hit"]), newly_missing=0,
                still_missing=len(y["missing"]), still_missing_SHA256=digest_keys(y["missing"]))
        if dut in NEW:
            directed = next(after for key, _, after in PAIRS if key == dut)
            assert witness(FULL, dut)["witness"] == witness(directed, dut)["witness"]
            assert targets(db, dut)["known_cause_target_hit"] == 960
            expected_inputs = a["artifact"]["input_files"] + 1
        else:
            assert sha256_file(da) == sha256_file(db)
            expected_inputs = a["artifact"]["input_files"]
        assert b["artifact"]["input_files"] == expected_inputs
        if dut not in primary_a:
            aa, bb = node_summaries(BASE, dut + ".summary.json"), node_summaries(FULL, dut + ".summary.json")
            assert len(bb) == expected_inputs and all(bb[n] == v for n, v in aa.items())
            all_nodes |= {xml_node(node) for node in bb}
        row = dict(dut=dut, native_build_id=b["artifact"]["build"]["build_id"], metrics=metrics,
            original_native_inputs=a["artifact"]["input_files"], current_native_inputs=expected_inputs,
            before_dat_SHA256=sha256_file(da), after_dat_SHA256=sha256_file(db),
            original_source_line_coverage=line_delta(source_lines(a, da, dut), source_lines(b, db, dut)))
        if dut in NEW:
            row["target_domains"] = dict(before=targets(da, dut), after=targets(db, dut))
            row["compact_witness"] = {key: value for key, value in witness(FULL, dut).items() if key != "witness"}
        rows.append(row)
    assert len(rows) == 9 and all_nodes == set(new)
    result = dict(format="lsq-Replay-cause-lifetime-contributor-v1", run=FULL, baseline_run=BASE, status=status,
        old_nodes=1762, current_nodes=1765, added_passing_nodes=3, original_failure_SHA256=failure_digest(old),
        current_failure_SHA256=failure_digest(new), rows=rows, source_aggregate=src["aggregate_SHA256"], old_sources=old_sources(), calibration=calibration(),
        coverage_monotonicity=dict(name="all_old_native_hits_retained", passed=True, status="PASS", failed_duts=[], newly_missing_toggle_points=0, required=True, waived=False),
        verification=dict(all1762old_outcomes_and196failure_details_equal=True, all9complete_original_build_contributors_kept=True,
            all3full_witnesses_equal_directed=True, all_original_streams_and_native_hits_kept=True,
            same_builds_and3point_universes=True, native_inputs_match_complete_primary_journal_node_sets=True,
            every_original_and_feedback_S3_lastBeat_equals_fixed32B_PA_bit5=True,
            locked_analyzer_and_all_native_build_files_SHA256s=True, no_native_coverage_OR_or_denominator_reduction=True),
        limits="Complete9build after, not expanded38DUT acceptance. All196functionalFAILs and unified227FAILs remain; cause/NC/Store and other domains still require their own evidence.")
    write_report(ROOT / "results" / FULL / "Replay-cause-lifetime-contributor-evidence-v1.json", result)
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("--full", action="store_true"); args = parser.parse_args()
    for pair in PAIRS:
        r = audit_pair(*pair)
        print(json.dumps({key: r[key] for key in ("dut", "metrics", "verification")}, indent=2))
    if args.full:
        print(json.dumps(audit_full(), indent=2))
