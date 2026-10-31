#!/usr/bin/env python3
"""Audit legal scalar owners, full public slots and actual native deltas."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from audit_checkpoint_pool_v1 import validate_run
from audit_coverage_points_v1 import records, sha256_file, summarize
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases, failure_digest
from audit_gap_closure_v1 import audit as delta, digest_keys, native, point_sets, point_key
from audit_load_raw_owners_v1 import FULL as PRIOR, FULL_PATHS as PRIOR_PATHS
from audit_native_case_probe_v1 import stable_run, journal_streams, xml_node
from audit_native_contributor_scope_v1 import contributors, same_summary
from audit_sq_head_permit_domain_v1 import source, evidence
from audit_store_strict_lifetimes_v1 import source_lines
from audit_uq_page_pairs_v1 import node_summaries
from audit_vsq_release_windows_v1 import line_delta
from run_summary import aggregate

ROOT = Path(__file__).resolve().parents[1]
FULL = "normal-replay-metadata-contributor-regression-01"
REPLAY_BASE = "normal-replay-original-contributors-01"
REPLAY_PATHS = ["tests/replay", "tests/sq_endpoint/test_replay_raw_boundary.py", "tests/sq_endpoint/test_replay_raw_pool.py"]
FULL_PATHS = PRIOR_PATHS + REPLAY_PATHS
PATHS = ("refill", "l2", "tlb-fast", "tlb-slow")
PAIRS = (
    ("load_queue_replay", "lrq-normal-metadata-baseline-02", "lrq-normal-metadata-after-02"),
    ("load_queue", "lq-normal-metadata-baseline-02", "lq-normal-metadata-after-02"),
    ("lsq_wrapper", "lsq-normal-metadata-baseline-02", "lsq-normal-metadata-after-02"),
)
FILES = {
    "load_queue_replay": "tests/replay/test_normal_metadata.py",
    "load_queue": "tests/load_queue/test_normal_replay_metadata.py",
    "lsq_wrapper": "tests/lsq_wrapper/test_normal_replay_metadata.py",
}


def load(path):
    return json.loads(path.read_text())


def original_sources():
    old = load(ROOT / "results" / PRIOR / "source-aggregate-launch.json")
    extra = {'lsqverify': {'lsqverify/normal_replay_metadata.py'},
        "tests": {*FILES.values(), "tests/normal_replay_probe/test_probe.py"}}
    rows = {}
    for group, excluded in extra.items():
        pairs = [(str(p.relative_to(ROOT)), sha256_file(p)) for p in (ROOT / group).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc" and str(p.relative_to(ROOT)) not in excluded]
        result = aggregate(pairs)
        assert result == old["groups"][group]
        rows[group] = dict(original_aggregate=result, added_files={name: sha256_file(ROOT / name) for name in sorted(excluded)})
    for group in ("pytest.ini", "manifest", "README.md"):
        if group == "manifest":
            result = aggregate([(str(p.relative_to(ROOT)), sha256_file(p)) for p in (ROOT / group).rglob("*") if p.is_file()])
        else:
            result = aggregate([(group, sha256_file(ROOT / group))])
        assert result == old["groups"][group]
    return dict(groups=rows,original162library_and198test_files_SHA256_equal=True,
        old_config_manifest_and_README_equal=True,old1569_DUT_run_repeated=False)


def producer_source():
    path = ROOT / "results" / PRIOR / "normal-replay-source-projection-triage-v1.json"
    prior = load(path)
    for row in prior["ranges"]:
        relative = row["path"].removeprefix("src/main/scala/xiangshan/")
        assert evidence(*source(relative), row["start_line"], row["end_line"], row["checked_expressions"]) == row
    ftq_path = ROOT / "results/normal-replay-metadata-probe-01/FTQ-source-projection-correction-v1.json"
    correction = load(ftq_path)
    for row in correction["source_ranges"]:
        relative = row["path"].removeprefix("src/main/scala/xiangshan/")
        assert evidence(*source(relative), row["start_line"], row["end_line"], row["checked_expressions"]) == row
    return dict(evidence=str(path.relative_to(ROOT)), evidence_SHA256=sha256_file(path),
        FTQ_source_correction=str(ftq_path.relative_to(ROOT)), FTQ_source_correction_SHA256=sha256_file(ftq_path),
        fixed_source_ranges_checked=len(prior["ranges"]),
        normal_scalar_opcodes=[0, 16, 2, 18, 4, 20, 6], output_Replay_fullva_is_VA50_zero_extension=True,
        first_issue_canonical64_not_confused_with_Replay_fullva=True,
        current_and_decoy_external_owners_bounded_by16=True,native_external_allocator_proven=False)


def id_padding_source_proof():
    rows = []
    for dut in FILES:
        path = ROOT / "dut" / dut / "LoadQueueReplayDut.v" if dut == "load_queue_replay" else ROOT / "rtl" / dut / "LoadQueueReplay.sv"
        raw = path.read_text()
        pinned = load(ROOT / "rtl" / dut / "source.json")["files"]["LoadQueueReplay.sv"]
        assert sha256_file(path) == pinned
        defs = {name: (int(width) + 1, expr.strip()) for width, name, expr in re.findall(
            r"wire\s+\[(\d+):0\]\s+(\w+)\s*=\s*([^;]+);", raw)}
        families = []
        for family, field in (("missMSHRId", "io_enq_{}_bits_rep_info_mshr_id"), ("tlbHintId", "io_enq_{}_bits_rep_info_tlb_id")):
            names = {f"{family}_{i}" for i in range(120)}
            declarations = re.findall(r"\breg\s+\[4:0\]\s+(" + family + r"_\d+)\s*;", raw)
            assert set(declarations) == names and len(declarations) == 120
            resets = dynamic = 0
            for match in re.finditer(r"\b(" + family + r"_\d+)\s*<=\s*([^;]+);", raw):
                expr = match[2].strip()
                if expr == "5'h0":
                    resets += 1
                else:
                    width, rhs = defs[expr]
                    assert width == 5 and rhs in ["{1'h0, " + field.format(i) + "}" for i in range(3)]
                    dynamic += 1
            assert resets == 120 and dynamic == 360
            for lane in range(3):
                assert re.search(r"input\s+\[3:0\]\s+" + field.format(lane) + r"\s*,", raw)
            families.append(dict(family=family, registers=120, reset_zero_writes=resets,
                clocked_exact4bit_zero_extension_writes=dynamic, registered_bits=5, native_input_bits=4,
                high_bit_native_direction_points_retained=240))
        rows.append(dict(dut=dut, source=str(path.relative_to(ROOT)), source_SHA256=pinned, families=families))
    report = dict(format="lsq-normal-replay-ID-padding-source-boundary-v1", rows=rows,
        classification="POST_RESET_FOUR_BIT_INPUT_ZERO_EXTENDED_TO_FIVE_BIT_REGISTER", native_dynamic_coverage_gain=0,
        verification=dict(all120registers_each_family_each_DUT=True, all_clocked_and_reset_writes_checked=True,
            exact4bit_public_ID_inputs=True, original_source_SHA256s=True),
        limits="Post-reset clocked source/configuration boundary only. Startup/fault injection is not proven. All1200MSHR/1200TLB native points per DUT remain; legal low4 bits can toggle but the fifth is never driven through an illegal16..31ID. No original coverage numerator or denominator is edited.")
    write_report(ROOT / "results" / REPLAY_BASE / "ID-padding-source-boundary-v1.json", report)
    return report


def calibration():
    correction_path = ROOT / "results/normal-replay-metadata-probe-01/FTQ-source-projection-correction-v1.json"
    ftq = load(correction_path)
    assert ftq["corrected_producer_SHA256"] == sha256_file(ROOT / "normal_replay_metadata.py")
    assert ftq["old_bytes_reconstructed_and_entire_library_aggregate_verified"]
    historical = []
    for after in ("lrq-normal-metadata-after-01", "lq-normal-metadata-after-01", "lsq-normal-metadata-after-01"):
        path = ROOT / "results" / after / "normal-replay-metadata-evidence-v1.json"
        report = load(path)
        assert not report["FTQ_frontend_admission"]["proven"]
        historical.append(dict(run=after, evidence=str(path.relative_to(ROOT)), SHA256=sha256_file(path),
            domain=report["FTQ_frontend_admission"]["domain"], original_native_results_retained=True))
    scope_path = ROOT / "results" / REPLAY_BASE / "baseline-scope-correction-v1.json"
    scope = load(scope_path)
    assert scope["first_audit_exitstatus"] == 1 and scope["actual_full_baseline_nodes"] == 181
    assert sha256_file(ROOT / scope["original_first_failed_audit_log"]) == scope["original_first_failed_audit_log_SHA256"]
    return dict(FTQ_source_correction=str(correction_path.relative_to(ROOT)), FTQ_source_correction_SHA256=sha256_file(correction_path),
        historical_interface_domain_runs=historical, original_baseline_count_audit_failure=scope,
        corrected_formal02_uses64B_and_ending_halfword_offset=True, original_181node_DUT_baseline_reexecuted=False,
        native_upstream_Frontend_or_allocator_proven=False)


def target_summary(dat, dut):
    source = ROOT / "dut" / dut / "LoadQueueReplayDut.v" if dut == "load_queue_replay" else ROOT / "rtl" / dut / "LoadQueueReplay.sv"
    points = [p for p in records(dat) if p["t"] == "toggle" and p["f"] == str(source)]
    patterns = {
        "vaddr": (r"vaddr_\d+\[(\d+)\]:(0->1|1->0)", set(range(50)), 12000),
        "opcode": (r"uop_\d+_fuOpType\[(\d+)\]:(0->1|1->0)", {1, 2, 4}, 2880),
        "MSHR_id": (r"missMSHRId_\d+\[(\d+)\]:(0->1|1->0)", set(range(4)), 1200),
        "TLB_hint_id": (r"tlbHintId_\d+\[(\d+)\]:(0->1|1->0)", set(range(4)), 1200),
    }
    result = {}
    for name, (pattern, legal_bits, expected) in patterns.items():
        selected = [p for p in points if re.fullmatch(pattern, p["o"])]
        assert len(selected) == expected, (dut, name, len(selected))
        target = [p for p in selected if int(re.fullmatch(pattern, p["o"])[1]) in legal_bits]
        rest = [p for p in selected if int(re.fullmatch(pattern, p["o"])[1]) not in legal_bits]
        result[name] = dict(hit=sum(p["hit"] > 0 for p in selected), total=len(selected),
            known_legal_write_bits=sorted(legal_bits), legal_target_hit=sum(p["hit"] > 0 for p in target),
            legal_target_total=len(target), remaining_other_domain_missing=sum(not p["hit"] for p in rest),
            missing_point_set_SHA256=digest_keys({point_key(p) for p in selected if not p["hit"]}),
            classification="existing_feature_legal_scalar_and_dependency_case" if name == "vaddr" else
                "normal scalar subset; other opcode domains remain" if name == "opcode" else
                "low4 valid input identity bits; registered fifth bit retained, never drive16..31",
            source=str(source.relative_to(ROOT)), source_lines=sorted({int(p["l"]) for p in selected}))
    return result


def witness_rows(run, dut, per_profile=120):
    paths = [p for p in (ROOT / "results" / run / "cases").rglob("normal-replay-metadata-witness.json") if load(p)["dut"] == dut]
    result = {}
    # Independently restate the source contract, rather than call producer.make
    # or the frozen model to manufacture a passing expected witness.
    opcodes = (0, 16, 2, 18, 4, 20, 6, 0)
    low48 = (0, (1 << 48) - 1, 0x555555555554, 0xAAAAAAAAAAAA, 0x333333333330, 0xCCCCCCCCCCFC, 0x123456780008, 0)
    for path in paths:
        item = load(path)
        assert item["path"] not in result and item["passed"] and item["error"] is None
        assert item["per_profile"] == per_profile and len(item["pools"]) == 8 and len(item["rows"]) == 8 * per_profile
        assert item["original_UID_completions"] == item["actual_grants"] == item["actual_feedbacks"] == 8 * per_profile
        assert item["peak_active_Loads"] == 1 and item["declared_peak_external_dependency_owners"] == 2
        assert item["declared_external_ID_capacity"] == 16 and item["resets_between_profiles"] == 0
        assert not item["native_upstream_allocator_proven"]
        for phase, pool in enumerate(item["pools"]):
            rows = item["rows"][phase * per_profile:(phase + 1) * per_profile]
            assert pool["phase"] == phase and pool["completed"] == per_profile
            slots = [row["public_slot"] for row in rows]
            assert len(set(slots)) == per_profile and pool["actual_slots"] == sorted(slots)
            if per_profile == 120:
                assert set(slots) == set(range(120))
            for index, row in enumerate(rows):
                ordinal = phase * per_profile + index
                address = low48[phase] | (3 << 48 if low48[phase] >> 47 else 0)
                fullva = address | (((1 << 14) - 1) << 50 if address >> 49 else 0)
                size = opcodes[phase] >> 1 & 7
                identity = 0 if phase in (0, 7) else 15 if phase == 1 else (index + phase) % 16
                assert row["uid"] == ordinal + 1 and row["ROB_ordinal"] == row["LQ_position"] == ordinal
                assert row["phase"] == phase and row["index"] == index and row["opcode"] == opcodes[phase]
                assert row["vaddr50"] == row["actual_Replay_fullva_zero_extended"] == address
                assert row["first_fullva64"] == fullva and row["size"] == size
                assert row["PA"] == 0x80000000 + ordinal * 4096 + address % 4096
                assert row["PA"] % 4096 == address % 4096 and address % (1 << size) == 0
                assert row["mask"] == ((1 << (1 << size)) - 1) << (address % 16)
                assert row["last_beat"] == bool(row["PA"] & 64)
                assert row["checkpoint"] == ((ordinal + 1) * 0x9E3779B97F4A7C15) % (1 << 64)
                assert row["FTQ_flag"] == ordinal // 1024 % 2 and row["FTQ_value"] == ordinal // 16 % 64
                assert row["FTQ_end_halfword_offset"] == 2 * (ordinal % 16) + 1
                assert row["dependency_ID"] == identity and row["decoy_ID"] == (identity + 1) % 16
                assert row["channel"] == (index + phase) % 2 and row["bank"] == row["public_slot"] % 3
                first = row["last_beat"] if row["keyword"] else not row["last_beat"]
                latency = 0 if item["path"] == "tlb-fast" else 2 if item["path"] == "l2" and first else 4
                assert row["first_offer_tick"] == row["matched_pulse_tick"] + latency
                assert row["matched_pulse_tick"] == row["wrong_pulse_tick"] + 10
                assert row["grant_tick"] == row["first_offer_tick"] + 8 and row["feedback_tick"] == row["grant_tick"] + 6
                assert row["actual_release_tick"] >= row["feedback_tick"] + (0 if dut == "load_queue_replay" else 4)
                assert row["hold_cycles"] == 3 and not row["first_S3_updateAddrValid"] and row["final_S3_updateAddrValid"]
                assert row["actual_local_completion"] and len(row["payload_SHA256"]) == 64
        result[item["path"]] = dict(path=str(path.relative_to(ROOT)), SHA256=sha256_file(path), witness=item)
    assert set(result) == set(PATHS)
    return result


def audit_pair(dut, before, after):
    a, b = validate_run(before, dut), validate_run(after, dut)
    assert a["source"] == b["source"]
    old, new = cases(before), cases(after)
    added = set(new) - set(old)
    assert len(added) == 4 and all(new[node] == value for node, value in old.items())
    assert all(node.startswith(FILES[dut][:-3].replace("/", ".") + "::") and new[node]["outcome"] == "PASS" for node in added)
    aa, bb = node_summaries(before, dut + ".summary.json"), node_summaries(after, dut + ".summary.json")
    assert all(bb[node] == value for node, value in aa.items())
    closure = delta(before, after, dut, dut.upper() + "-NORMAL-SCALAR-REPLAY-METADATA", FILES[dut] + "::four_paths")
    assert all(closure["verification"].values())
    targets = dict(before=target_summary(a["dat"], dut), after=target_summary(b["dat"], dut))
    assert all(row["legal_target_hit"] == row["legal_target_total"] for row in targets["after"].values())
    ws = witness_rows(after, dut)
    probe = witness_rows("normal-replay-metadata-probe-02", dut, per_profile=2)
    report = dict(format="lsq-normal-replay-metadata-evidence-v1", dut=dut, before_run=before, after_run=after,
        contract="docs/contracts/normal-load-replay-metadata.md", baseline_tests=len(old), after_tests=len(new),
        added_nodes=sorted(added), native_build_id=closure["native_build_id"], source_aggregate=a["source"]["aggregate_SHA256"],
        raw_nonwrapper_metrics=closure["metrics"], target_domains=targets,
        original_source_line_coverage=line_delta(source_lines(a["meta"], a["dat"], dut), source_lines(b["meta"], b["dat"], dut)),
        witnesses=[dict(path=path, file=v["path"], SHA256=v["SHA256"]) for path, v in ws.items()],
        calibration_probe=dict(run="normal-replay-metadata-probe-02", passing_nodes=12,
            current_layer_UIDs=sum(v["witness"]["original_UID_completions"] for v in probe.values())),
        producer_source=producer_source(), calibration=calibration(), ID_padding_source_boundary=id_padding_source_proof(),
        verification=dict(actual_native_DUT_full_frozen_reference=True, all4paths_8profiles_120public_slots_checked=True,
            original_UID_public_metadata_and_exact_wakeup_checked=True, wrong_live_ID_did_not_unlock=True,
            known_writes_vaddr12000_opcode720_MSHR960_TLB960_directions_hit=True,
            all_old_results_streams_and_native_hits_kept=True, same_source_build_and_all3point_universes=True,
            S0_grant_same_bank_S3_original_slot_and_real_release=True, no_private_state_stimulus_or_midprogram_reset=True),
        limits="Normal scalar fixed-source boundary projection; sequential all-slot reuse is not simultaneous full-capacity proof or native upstream allocator/Cache/TLB/LDU/ROB validation. Fifth ID bit and other opcode/exception/vector domains remain in denominator. All historical failures are kept in separate full contributor evidence; this directed PASS is not whole-LSQ acceptance.")
    write_report(ROOT / "results" / after / "normal-replay-metadata-evidence-v1.json", report)
    return report


def audit_replay_baseline():
    status, source_set = stable_run(REPLAY_BASE)
    old_summaries = node_summaries("lsq-progress-regression-15", "load_queue_replay.summary.json")
    new_summaries = node_summaries(REPLAY_BASE, "load_queue_replay.summary.json")
    assert len(old_summaries) == 179 and len(new_summaries) == 181
    assert all(new_summaries[node] == value for node, value in old_summaries.items())
    old_cases = cases("lsq-progress-regression-15")
    baseline = cases(REPLAY_BASE)
    assert set(baseline) == {xml_node(node) for node in new_summaries}
    assert all(baseline[xml_node(node)] == old_cases[xml_node(node)] for node in old_summaries)
    added = set(baseline) - {xml_node(node) for node in old_summaries}
    assert added == {
        "tests.replay.test_pool_payload::test_checkpoint_high_low_lifetimes_at_every_public_replay_slot",
        "tests.replay.test_gap_closure::test_full_width_replay_metadata_and_pointer_identity_reuses_slot",
    }
    assert all(baseline[node]["outcome"] == "PASS" for node in added)
    assert status["manifest_tests"] == {"PASS": 177, "FAIL": 4} and status["pytest_exitstatus"] == 1
    meta, dat = native(REPLAY_BASE, "load_queue_replay")
    assert meta["artifact"]["input_files"] == 181
    assert len([a for a in meta["manifest"]["artifacts"] if a["kind"] == "native"]) == 1
    command = load(ROOT / "results" / REPLAY_BASE / "command.json")["command"]
    assert command[command.index("--lsq-trace-max-mb") + 2:] == REPLAY_PATHS + ["--ignore=" + FILES["load_queue_replay"], "--tb=short"]
    report = dict(format="lsq-normal-replay-complete-original-contributor-baseline-v1", run=REPLAY_BASE,
        status=status, original_unified_Replay_nodes=179, current_Replay_nodes=181,
        added_preexisting_nodes=sorted(added), outside_Replay_directory_contributors=48,
        original_failure_SHA256=failure_digest(baseline), original_results_and_streams_unchanged=True,
        source_aggregate=source_set["aggregate_SHA256"], native_dat_SHA256=sha256_file(dat),
        verification=dict(all179original_contributors_including48endpoint_nodes=True,
            extra_two_preexisting_nodes_passed=True, all4original_failures_preserved=True,
            no_old_eight_build1569_DUT_rerun=True, committed_single_build_baseline=True))
    write_report(ROOT / "results" / REPLAY_BASE / "normal-replay-complete-baseline-v1.json", report)
    return report


def audit_full():
    old_status, _ = stable_run(PRIOR)
    status, source_set = stable_run(FULL)
    rb = audit_replay_baseline()
    old = cases(PRIOR)
    old_replay = cases(REPLAY_BASE)
    assert not set(old) & set(old_replay)
    expected = dict(old, **old_replay)
    new = cases(FULL)
    assert len(expected) == 1750 and len(new) == 1762
    assert all(new[node] == value for node, value in expected.items())
    added = set(new) - set(expected)
    directed = set().union(*(set(cases(after)) - set(cases(before)) for _, before, after in PAIRS))
    assert added == directed and len(added) == 12 and all(new[node]["outcome"] == "PASS" for node in added)
    assert status["manifest_tests"] == {"PASS": 1566, "FAIL": 196} and status["pytest_exitstatus"] == 1
    assert failure_digest(expected) == failure_digest(new)
    command = load(ROOT / "results" / FULL / "command.json")["command"]
    assert command[command.index("--lsq-trace-max-mb") + 2:] == FULL_PATHS + ["--tb=short"]
    assert "--lsq-codec-cache" not in command and "-p" not in command
    a, b = contributors(PRIOR), contributors(FULL)
    for dut, items in a.items():
        assert all(same_summary(value, b[dut][node]) for node, value in items.items())
    assert len(b["lsq_wrapper"]) == 805
    streams_a, streams_b = journal_streams(PRIOR), journal_streams(FULL)
    assert len(streams_a) == 2403 and len(streams_b) == 2415
    assert all(streams_b[node] == value for node, value in streams_a.items())
    nodes = set().union(*(set(items) for items in b.values()))
    for dut in ("load_queue", "load_queue_uncache", "virtual_store_queue", "unalign_queue", "load_queue_replay"):
        baseline = REPLAY_BASE if dut == "load_queue_replay" else PRIOR
        aa, bb = node_summaries(baseline, dut + ".summary.json"), node_summaries(FULL, dut + ".summary.json")
        assert all(bb[node] == value for node, value in aa.items())
        assert len(bb) == len(aa) + (4 if dut in FILES else 0)
        m, _ = native(FULL, dut)
        assert m["artifact"]["input_files"] == len(bb)
        nodes |= {xml_node(node) for node in bb}
    assert nodes == set(new)
    rows = []
    for dut in ("forward_module", "physical_store_queue", "store_queue", "lsq_wrapper", "unalign_queue", "virtual_store_queue", "load_queue_uncache", "load_queue", "load_queue_replay"):
        baseline = REPLAY_BASE if dut == "load_queue_replay" else PRIOR
        ma, da = native(baseline, dut)
        mb, db = native(FULL, dut)
        assert ma["artifact"]["build"] == mb["artifact"]["build"]
        parsed = summarize(db, mb["artifact"]["build"], mb["artifact"])
        assert parsed["raw_parser_matches_analyzer"] and parsed["coverage_artifact_matches_dat"]
        for path, digest in mb["artifact"]["build"]["files"].items():
            assert sha256_file(Path(path)) == digest
        aa, bb = point_sets(da), point_sets(db)
        metrics = {}
        for kind in aa:
            assert aa[kind]["all"] == bb[kind]["all"] and aa[kind]["hit"] <= bb[kind]["hit"]
            metrics[kind] = dict(before_hit=len(aa[kind]["hit"]), after_hit=len(bb[kind]["hit"]), total=len(bb[kind]["all"]),
                newly_hit=len(bb[kind]["hit"] - aa[kind]["hit"]), newly_hit_SHA256=digest_keys(bb[kind]["hit"] - aa[kind]["hit"]),
                newly_missing=0, still_missing=len(bb[kind]["missing"]), still_missing_SHA256=digest_keys(bb[kind]["missing"]))
        row = dict(dut=dut, baseline_run=baseline, native_build_id=mb["artifact"]["build"]["build_id"], metrics=metrics,
            before_dat_SHA256=sha256_file(da), after_dat_SHA256=sha256_file(db),
            original_native_inputs=ma["artifact"]["input_files"], current_native_inputs=mb["artifact"]["input_files"],
            original_source_line_coverage=line_delta(source_lines(ma, da, dut), source_lines(mb, db, dut)))
        if dut in FILES:
            directed_run = next(after for key, _, after in PAIRS if key == dut)
            full_ws, directed_ws = witness_rows(FULL, dut), witness_rows(directed_run, dut)
            assert {key: value["witness"] for key, value in full_ws.items()} == {key: value["witness"] for key, value in directed_ws.items()}
            row["target_domains"] = dict(before=target_summary(da, dut), after=target_summary(db, dut))
            assert all(value["legal_target_hit"] == value["legal_target_total"] for value in row["target_domains"]["after"].values())
        else:
            assert sha256_file(da) == sha256_file(db)
        rows.append(row)
    prior = load(ROOT / "results" / PRIOR / "load-RAW-owners-contributor-evidence-v1.json")
    report = dict(format="lsq-normal-replay-metadata-contributor-v1", run=FULL, baseline_run=PRIOR,
        baseline_Replay_run=REPLAY_BASE, status=status, source_aggregate=source_set["aggregate_SHA256"],
        old_eight_build_nodes=1569, extra_preexisting_Replay_nodes=181, baseline_nodes=1750, current_nodes=1762,
        added_passing_nodes=12, original_failures=196, original_failure_SHA256=failure_digest(expected),
        current_failure_SHA256=failure_digest(new), old_eight_build_status=old_status, original_sources=original_sources(),
        replay_complete_baseline=rb, rows=rows, producer_source=producer_source(), calibration=calibration(),
        ID_padding_source_boundary=id_padding_source_proof(),
        required_new_functional_failures=prior["required_new_functional_failures"], prior_domain_limited_evidence=prior["prior_domain_limited_evidence"],
        coverage_monotonicity=dict(name="all_old_native_hits_retained", passed=True, status="PASS", failed_duts=[], newly_missing_toggle_points=0, required=True, waived=False),
        verification=dict(actual_fresh_complete_nine_build_after=True, all1750old_outcomes_and196failure_details_equal=True,
            complete_original_native_contributors_including48Replay_endpoint_nodes=True,
            same_builds_and_all3point_universes=True, all_old_native_hits_and_streams_kept=True,
            all12full_witnesses_equal_directed=True, source_correct_normal_scalar_lifetimes_checked=True,
            all_original_library_tests_and_config_SHA256_equal=True, old1569DUT_baseline_not_repeated=True,
            locked_analyzer_and_native_hashes_checked=True, no_native_coverage_OR_or_denominator_reduction=True),
        limits="Nine actual build contexts, not new38DUT acceptance. The196FAIL total adds4preexisting Replay failures to the previous192; it is not a new failure or a changed old signature. Scalar boundary-source stimulus and external ID ownership projection do not prove native upstream allocation or Cache read data; fifth ID bit,other opcodes,exceptions and prior domains remain. Unified2330/227FAIL remains untouched.")
    write_report(ROOT / "results" / FULL / "normal-replay-metadata-contributor-evidence-v1.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--replay-baseline-only", action="store_true")
    args = parser.parse_args()
    if args.replay_baseline_only:
        print(json.dumps(audit_replay_baseline(), indent=2))
    else:
        for pair in PAIRS:
            row = audit_pair(*pair)
            print(json.dumps({key: row[key] for key in ("dut", "baseline_tests", "after_tests", "raw_nonwrapper_metrics", "verification")}, indent=2))
        if args.full:
            print(json.dumps(audit_full(), indent=2))
