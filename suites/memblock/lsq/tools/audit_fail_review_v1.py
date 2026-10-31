#!/usr/bin/env python3
"""Audit first-failure inventory and independent, bounded FAIL reproductions.

No DUT execution and no import of a domain reference model. Prior issue records
nominate families; only actual public events and fixed-source checks adjudicate.
"""
from collections import Counter, defaultdict
import ast
import hashlib
import itertools
import json
from pathlib import Path
import re
import subprocess

from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases, failure_digest
from audit_sq_head_permit_domain_v1 import source, evidence, REPO, COMMIT
from run_summary import aggregate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fail-review-baseline-01"
UNIFIED = "lsq-progress-regression-15"
LATEST = "replay-cause-lifetimes-contributor-regression-03"
RUNS = ("fail-review-independent-01", "fail-review-independent-02", "fail-review-independent-03", "fail-review-domain-controls-01")
CURRENT_PROBES = {"DEQ-WB-001": RUNS[0], "RAR-REL-001": RUNS[0], "LRQ-STRICT-001": RUNS[1], "LQU-SID-001": RUNS[2]}


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(path):
    return dict(path=str(path.relative_to(ROOT)), SHA256=sha(path))


def guard_old():
    guard = load(OUT / "preflight-guard-v1.json")
    assert all(sha(ROOT / name) == digest for name, digest in guard["protected_SHA256s"].items())
    exclusions = {"tests": {"tests/fail_review/conftest.py", "tests/fail_review/test_public_contracts.py"},
        "tools": {"tools/audit_fail_review_v1.py"}}
    groups = {}
    for group, old in guard["old_source_groups"].items():
        base = ROOT / "docs/contracts" if group == "docs" else ROOT / group
        paths = [p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"] if base.is_dir() else [base]
        pairs = [(str(p.relative_to(ROOT)), sha(p)) for p in paths if str(p.relative_to(ROOT)) not in exclusions.get(group, set())]
        actual = aggregate(pairs)
        assert actual == old, ("preexisting source changed", group, old, actual)
        groups[group] = actual
    return dict(protected_artifacts=len(guard["protected_SHA256s"]), old_source_groups=groups,
        all_old_artifact_SHA256s_equal=True, no_existing_model_fixture_test_RTL_or_index_edited=True)


def audit_runs():
    result, builds = [], {}
    for name in RUNS:
        path = ROOT / "results" / name
        manifest = load(path / "execution/manifest.json")
        assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
        data = cases(name)
        counts = dict(Counter(row["outcome"] for row in data.values()))
        assert counts == manifest["tests"] and not set(counts) - {"PASS", "FAIL"}
        launch, end = load(path / "source-aggregate-launch.json"), load(path / "source-aggregate-end.json")
        assert end.pop("launch_and_end_equal") and launch == end
        policy = load(path / "trace-policy.json")
        assert not policy["per_cycle_JSON"] and not policy["waveforms"]
        assert not any(p.suffix in (".jsonl", ".fst", ".vcd") for p in (path / "cases").rglob("*"))
        artifacts = []
        for artifact in manifest["artifacts"]:
            p = Path(artifact["path"])
            assert sha(p) == artifact["sha256"]
            artifacts.append(dict(path=str(p.relative_to(ROOT)), SHA256=sha(p), kind=artifact["kind"]))
            if artifact["kind"] == "native":
                build = artifact["build"]
                if build["build_id"] not in builds:
                    assert all(sha(Path(filename)) == digest for filename, digest in build["files"].items())
                    builds[build["build_id"]] = build
        result.append(dict(run=name, tests=counts, native_builds=sum(a["kind"] == "native" for a in manifest["artifacts"]),
            JUnit=identity(path / "pytest.xml"), manifest=identity(path / "execution/manifest.json"),
            source_files=launch["file_count"], source_launch_end_equal=True, artifacts=artifacts))
    return result


def witnesses():
    selected = defaultdict(list)
    for issue, run in CURRENT_PROBES.items():
        run_cases = cases(run)
        for path in sorted((ROOT / "results" / run / "cases").rglob("fail-review-witness.json")):
            w = load(path)
            if w["metadata"]["issue"] != issue:
                continue
            assert w["probe_completed"] and w["no_model_or_private_state_oracle"]
            assert w["failures"] == [row for row in w["checks"] if not row["passed"]]
            node = w["nodeid"].replace(".py::", "::").replace("/", ".")
            assert run_cases[node]["outcome"] == ("FAIL" if w["failures"] else "PASS")
            for check in w["checks"]:
                assert check["passed"] == (check["actual"] == check["expected"])
            selected[issue].append((path, w))
    assert {key: len(value) for key, value in selected.items()} == {"DEQ-WB-001": 6, "RAR-REL-001": 8, "LRQ-STRICT-001": 12, "LQU-SID-001": 6}
    return selected


def selected_events(w, name):
    return [row for row in w["events"] if row["event"] == name]


def check_semantics(selected):
    evidence_rows = {}
    for issue, items in selected.items():
        rows = []
        for path, w in items:
            meta = w["metadata"]
            expected_fail = False
            if issue == "LQU-SID-001":
                requests = selected_events(w, "bus_request_fire")
                acks = selected_events(w, "SID_ack")
                responses = selected_events(w, "response_valid_SID_returned")
                consumed = selected_events(w, "original_UID_s2_response")
                assert len(requests) == len(acks) == len(responses) == len(consumed) == 2
                assert [r["uid"] for r in requests] == [1, 2]
                assert len({r["mid"] for r in acks}) == 2 and all(0 <= r["mid"] < 16 for r in acks)
                assert all(requests[i]["mid"] == acks[i]["mid"] for i in range(2))
                assert responses[0]["tick"] < acks[1]["tick"]
                assert acks[1]["sid"] == (4 if meta["mode"] == "different_sid" else 3)
                assert responses[0]["sid"] == 3 and responses[1]["sid"] == acks[1]["sid"]
                assert responses[0]["data"] == 0x0123456789ABCDEF and responses[1]["data"] == 0xFEDCBA9876543210
                assert not responses[0]["error"] and responses[1]["error"] == meta["new_error"]
                assert len(selected_events(w, "LDU_S3_input")) == 2
                for owner in (1, 2):
                    response = next(r for r in responses if r["uid"] == owner)
                    out = next(r for r in consumed if r["uid"] == owner)
                    correct = dict(data=response["data"] * ((1 << 64) + 1), derr=int(response["error"]), nderr=0, s1_error=int(response["error"]))
                    actual = {key: out[key] for key in correct}
                    if owner == 1 and meta["mode"] == "reuse_unconsumed":
                        assert out["tick"] > responses[1]["tick"]
                        assert actual["data"] == responses[1]["data"] * ((1 << 64) + 1)
                        assert actual["derr"] == actual["s1_error"] == int(meta["new_error"])
                        assert actual != correct
                    else:
                        assert actual == correct
                if meta["mode"] == "consume_first":
                    assert consumed[0]["tick"] < acks[1]["tick"]
                expected_fail = meta["mode"] == "reuse_unconsumed"
            elif issue == "DEQ-WB-001":
                req, resp, fire = (selected_events(w, key) for key in ("Cache_request_fire", "Cache_response_fire", "WB_actual_fire"))
                held = selected_events(w, "held_writeback")
                assert len(req) == len(resp) == len(fire) == 1 and len(held) == meta["stall"]
                assert req[0]["tick"] < resp[0]["tick"] < fire[0]["tick"]
                assert resp[0]["denied"] == meta["denied"] and resp[0]["corrupt"] == meta["corrupt"]
                assert not resp[0]["writeback_ready"] and fire[0]["ready"] and fire[0]["valid"]
                if meta["stall"]:
                    assert all(r["valid"] and not r["ready"] and r["denied"] == r["corrupt"] == 0 for r in held)
                    assert fire[0]["denied"] == fire[0]["corrupt"] == 0
                else:
                    assert fire[0]["denied"] == int(meta["denied"]) and fire[0]["corrupt"] == int(meta["corrupt"])
                expected_fail = bool(meta["stall"])
            elif issue == "RAR-REL-001":
                enq, answer = selected_events(w, "younger_load_allocation"), selected_events(w, "older_load_violation_response")
                assert len(enq) == len(answer) == 1 and answer[0]["tick"] == enq[0]["tick"] + 2
                assert enq[0]["ROB"] == 2 and enq[0]["LQ"] == 2 and enq[0]["head_LQ"] == 0
                assert answer[0]["ROB"] == 1 and answer[0]["valid"] == 1
                assert enq[0]["PA"] == answer[0]["PA"] == 0x18000 and enq[0]["no_revoke"]
                if meta["distance"]:
                    pulse = selected_events(w, "release")
                    assert len(pulse) == 1 and enq[0]["tick"] - pulse[0]["tick"] == 2 * meta["distance"]
                expected = bool(meta["data_valid"] and meta["distance"] in (0, 1))
                actual = bool(meta["data_valid"] and meta["distance"] in (0, 2))
                assert bool(answer[0]["nuke"]) == actual
                expected_fail = actual != expected
            else:
                dirty, window, release, grant, feedback = (selected_events(w, key) for key in (
                    "disabled_feedback_input", "strict_blocked_window_end", "legal_dependency_release",
                    "actual_Replay_grant_after_legal_release", "same_public_slot_success_feedback"))
                assert len(dirty) == len(window) == len(release) == len(grant) == len(feedback) == 1
                assert dirty[0]["valid"] == 0 and dirty[0]["no_address_wakeup"] and dirty[0]["continuous_ready_pointer"] == 0
                early = window[0]["early_valid_observations"]
                expected_fail = meta["bitmap"] and meta["target"] == 0
                assert bool(early) == expected_fail
                assert all(r["strict"] == 1 and r["slot"] == 0 and r["tick"] < release[0]["tick"] for r in early)
                assert window[0]["tick"] < release[0]["tick"] <= grant[0]["tick"] < feedback[0]["tick"]
                assert grant[0]["public_slot"] == feedback[0]["slot"] == 0
                assert any(r["label"] == "original Replay owner actually freed" and r["actual"] == 0 and r["passed"] for r in w["checks"])
            assert bool(w["failures"]) == expected_fail
            rows.append(dict(**identity(path), nodeid=w["nodeid"], metadata=meta, verdict="FAIL" if expected_fail else "PASS",
                first_mismatch=w["failures"][0] if w["failures"] else None,
                recorded_checks=len(w["checks"]), all_named_protocol_obligations_independently_recomputed=True))
        evidence_rows[issue] = dict(run=CURRENT_PROBES[issue], tests=dict(Counter(r["verdict"] for r in rows)), rows=rows)
    return evidence_rows


def fixed_sources():
    ranges = []
    checks = (
        ("mem/lsqueue/LoadQueueUncache.scala", 94, 110, ["slaveAccept := true.B", "slaveAccept := false.B"]),
        ("mem/lsqueue/LoadQueueUncache.scala", 190, 197, ["io.uncache.resp.ready := true.B", "uncacheData := io.uncache.resp.bits.data"]),
        ("mem/lsqueue/LoadQueueUncache.scala", 432, 440, ["e.io.slaveId.valid && e.io.slaveId.bits === io.uncache.resp.bits.id"]),
        ("cache/dcache/Uncache.scala", 166, 171, ["valid := false.B", "waitReturn := false.B"]),
        ("cache/dcache/Uncache.scala", 493, 499, ["when(resp.fire)", "states(r0_canSentIdx).updateReturn()"]),
        ("mem/lsqueue/NewStoreQueue.scala", 1082, 1117, ["hasHardwareError := false.B", "hasAccessFault := false.B", "io.writeBack.valid := writeBackValid"]),
        ("mem/lsqueue/LoadQueueReplay.scala", 390, 402, ["!strict(i) && stAddrReadyVec", "storeAddrInSameCycleVec(i) :="]),
        ("mem/lsqueue/LoadQueueReplay.scala", 825, 865, ["Mux(enq.bits.isLoadReplay, enq.bits.schedIndex", "val enqFireBase = enq.fire && !cancelEnq(w)", "strict(enqIndex) := false.B"]),
        ("mem/lsqueue/LoadQueueRAR.scala", 130, 138, ["release signal should delay 1 cycle", "release2Cycle.valid := RegNext(io.release.valid)"]),
        ("mem/lsqueue/LoadQueueRAR.scala", 181, 189, ["release2Cycle.valid", "release1Cycle.valid"]),
        ("mem/lsqueue/LSQWrapper.scala", 498, 502, ["enq.valid && !io.redirect.valid", "toLsq.valid := RegNext(do_enq)"]),
        ("backend/CtrlBlock.scala", 817, 830, ["lsqEnqCtrl.io.redirect := s1_s3_redirect", "io.toMem.lsqEnqIO <> lsqEnqCtrl.io.enqLsq"]),
        ("backend/CtrlBlock.scala", 867, 867, ["io.redirect := s1_s3_redirect"]),
        ("backend/Backend.scala", 235, 235, ["io.mem.lsqEnqIO <> ctrlBlock.io.toMem.lsqEnqIO"]),
        ("backend/Backend.scala", 578, 578, ["io.mem.redirect := ctrlBlock.io.redirect"]),
        ("XSCore.scala", 150, 150, ["backend.io.mem.lsqEnqIO <> memBlock.io.ooo_to_mem.enqLsq"]),
        ("XSCore.scala", 210, 210, ["memBlock.io.redirect := backend.io.mem.redirect"]),
        ("mem/MemBlock.scala", 494, 494, ["val redirect = RegNextWithEnable(io.redirect)"]),
        ("mem/MemBlock.scala", 1055, 1058, ["lsq.io.enq            <> io.ooo_to_mem.enqLsq", "lsq.io.brqRedirect    <> redirect"]),
        ("mem/lsqueue/LSQWrapper.scala", 187, 204, ["io.enq.needAlloc(i)(1) && io.enq.req(i).valid", "storeQueue.io.redirect                      <> io.brqRedirect"]),
        ("mem/lsqueue/NewStoreQueue.scala", 2162, 2164, ["virtualStoreQueue.io.redirect   <> io.redirect", "virtualStoreQueue.io.enq        <> io.enq"]),
        ("backend/rob/Rob.scala", 1248, 1258, ["val pendingPtrInput = WireInit(deqPtr)", "io.lsq.pendingPtr :="]),
        ("mem/lsqueue/LoadQueueUncache.scala", 122, 126, ["val pendingPtr = GatedRegNext(io.rob.pendingPtr)", "req.uop.robIdx.isNotAfterSlot(pendingPtr)"]),
        ("Parameters.scala", 891, 892, ["def l1BusDataWidth = 256"]),
        ("cache/L1Cache.scala", 44, 44, ["def refillBytes = l1BusDataWidth / 8"]),
        ("mem/pipeline/NewLoadUnit.scala", 1613, 1613, ["lqWrite.rep_info.last_beat := paddr(log2Up(refillBytes))"]),
    )
    for filename, start, end, required in checks:
        ranges.append(evidence(*source(filename), start, end, required))
    gitlink = subprocess.check_output(["git", "ls-tree", COMMIT, "utility"], cwd=REPO, text=True).split()
    assert gitlink[0:2] == ["160000", "commit"]
    utility = REPO / "utility"
    for filename, required in (("src/main/scala/utility/BitUtils.scala", "next.valid := GatedValidRegNext(data.valid, false.B)"),
        ("src/main/scala/utility/ClockGatedReg.scala", "last := RegNext(next, init)")):
        data = subprocess.check_output(["git", "show", f"{gitlink[2]}:{filename}"], cwd=utility)
        assert (utility / filename).read_bytes() == data and required in data.decode()
        ranges.append(dict(repository="XiangShan/utility", commit=gitlink[2], path=filename,
            SHA256=hashlib.sha256(data).hexdigest(), checked_expressions=[required], working_bytes_equal_git_object=True))
    generated = []
    for dut, main, expressions in (
        ("load_queue_rar", "LoadQueueRAR", ["release2Cycle_valid <= release2Cycle_valid_REG;", "release2Cycle_valid_REG <= io_release_valid;"]),
        ("load_queue_uncache", "LoadQueueUncache", ["_entries_0_io_slaveId_valid & _entries_0_io_slaveId_bits == io_uncache_resp_bits_id"]),
        ("load_queue_uncache", "UncacheEntry", ["slaveAccept <= ~_GEN_0 & (slaveAck | ~writeback & slaveAccept);"]),
        ("deq_module", "DeqModule", ["~_GEN_5 & hasHardwareError", "~_GEN_5 & hasAccessFault"]),
        ("load_queue_replay", "LoadQueueReplay", [
            "io_enq_0_bits_isLoadReplay ? io_enq_0_bits_schedIndex : _freeList_io_allocateSlot_0;",
            "wire            _GEN_4 = enqIndex == 7'h0;", "_GEN_1580 = ~_GEN_4 & strict_0;"]),
        ("virtual_store_queue", "VirtualStoreQueue", ["always @(posedge clock or posedge reset)", "enqPtrVec_0_value <= 7'h0;", "deqPtrVec_0_value <= 7'h0;"]),
    ):
        path = ROOT / "rtl" / dut / (main + ".sv")
        text = path.read_text()
        locked = load(path.parent / "source.json")["files"][path.name]
        assert sha(path) == locked and all(value in text for value in expressions)
        lines = text.splitlines()
        generated.append(dict(**identity(path), checked_expressions=[dict(expression=value,
            lines=[i for i, line in enumerate(lines, 1) if value in line]) for value in expressions],
            surviving_assertion_or_fatal_lines=[i for i, line in enumerate(lines, 1) if re.search(r"\$fatal\b|\$error\b|\bassert\s*\(", line.split("//")[0])]))
    exports = []
    for dut, module, exported in (("load_queue_rar", "LoadQueueRAR", "LoadQueueRarDut"),
        ("load_queue_uncache", "LoadQueueUncache", "LoadQueueUncacheDut"),
        ("load_queue_replay", "LoadQueueReplay", "LoadQueueReplayDut"),
        ("deq_module", "DeqModule", "DeqModuleDut"),
        ("virtual_store_queue", "VirtualStoreQueue", "VirtualStoreQueueDut")):
        a, b = ROOT / "rtl" / dut / (module + ".sv"), ROOT / "dut" / dut / (exported + ".v")
        assert a.read_bytes() == b.read_bytes()
        exports.append(dict(dut=dut, original_RTL=identity(a), actual_native_export=identity(b), bytes_equal=True))
    rows = []
    for valid, red, recover, iq, alloc in itertools.product((False, True), repeat=5):
        dispatch_next = valid and not red and not recover and iq and alloc
        assert not (dispatch_next and red)
        rows.append((valid, red, recover, iq, alloc, dispatch_next))
    return dict(pinned_ranges=ranges, generated_mechanisms=generated, native_export_source_identity=exports,
        VSQ_normal_path_same_cycle_overlap_exclusion=dict(boolean_rows=len(rows),
            truth_SHA256=hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
            premise="LsqEnqCtrl gates with !redirect then registers valid; MemBlock registers the SAME redirect valid once; intervening connections have no additional dispatch delay.",
            scope="The named normal dispatch path and this exact overlap, not all VSQ or full-core reachability."),
        missing_assertions_not_used_as_legality_or_correctness_evidence=True)


def source_lineage():
    current = (ROOT / "tests/fail_review/test_public_contracts.py").read_text()
    second = current.replace('e.check("external response valid actually sampled", e.input["io_uncache_resp_valid"], 1)',
        'e.check("external response actual fire", e.pre["io_uncache_resp_ready"], 1)').replace(
        'e.event("response_valid_SID_returned", uid=owner["uid"], sid=sid, data=data, error=error,\n            response_ready_not_retained=True, acceptance_confirmed_by_following_original_LQ_wakeup=True)',
        'e.event("response_fire_SID_returned", uid=owner["uid"], sid=sid, data=data, error=error)')
    first = second.replace('e.check("LQU valid input actually sampled", e.input[p + "valid"], 1)',
        'e.check("LQU input accepted", e.pre[p + "ready"], 1)').replace(
        'e.check("new original strict Load allocated", e.post["io_replayAllocate"], 1)',
        'e.check("new original strict Load accepted", e.pre["io_enq_0_ready"], 1)')
    corrections = [load(ROOT / "results" / RUNS[0] / "probe-correction-v1.json"), load(ROOT / "results" / RUNS[1] / "probe-correction-v2.json")]
    assert hashlib.sha256(first.encode()).hexdigest() == corrections[0]["old_producer_test_SHA256"]
    assert hashlib.sha256(second.encode()).hexdigest() == corrections[1]["old_probe_test_SHA256"]
    for name in ("test_CBO_fault_belongs_to_actual_writeback_fire", "test_RAR_release_association_has_the_declared_age_window"):
        before = next(n for n in ast.parse(first).body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
        after = next(n for n in ast.parse(current).body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
        assert ast.dump(before) == ast.dump(after)
    name = "test_invalid_feedback_must_not_relax_a_live_strict_owner"
    before = next(n for n in ast.parse(second).body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    after = next(n for n in ast.parse(current).body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    assert ast.dump(before) == ast.dump(after)
    for filename in ("tests/fail_review/conftest.py", "tests/fail_review/test_public_contracts.py"):
        text = (ROOT / filename).read_text()
        assert not re.search(r"\b(?:skip|xfail)\b", text)
        assert not re.search(r"(?:from|import)\s+[^\n]*\.model\b", text)
    return dict(current_probe_sources=[identity(ROOT / "tests/fail_review/conftest.py"), identity(ROOT / "tests/fail_review/test_public_contracts.py")],
        correction_reports=[identity(ROOT / "results" / RUNS[0] / "probe-correction-v1.json"), identity(ROOT / "results" / RUNS[1] / "probe-correction-v2.json")],
        original_new_probe_source_bytes_reconstructed=True, completed_WB_RAR_and_strict_function_ASTs_unchanged=True,
        no_completed_independent_case_reexecuted_to_hide_a_failure=True, no_reference_model_import=True)


def domain_and_verification_errors():
    data, prior = cases(RUNS[3]), cases(UNIFIED)
    assert Counter(r["outcome"] for r in data.values()) == {"PASS": 6, "FAIL": 3}
    boundary = []
    for node, row in data.items():
        assert row["outcome"] == prior[node]["outcome"]
        if row["outcome"] != "FAIL":
            continue
        assert row["detail"].splitlines()[0] == prior[node]["detail"].splitlines()[0]
        boundary.append(dict(nodeid=node, classification="PRODUCER_DOMAIN_BOUNDARY",
            issue="VSQ-REDIR-IF-001" if ".vsq." in node else "LQU-MMIO-IF-001",
            current_first_assertion=row["detail"].splitlines()[0],
            exact_full_failure_detail_equal=row["detail"] == prior[node]["detail"],
            historical_detail_SHA256=hashlib.sha256(prior[node]["detail"].encode()).hexdigest(),
            fresh_detail_SHA256=hashlib.sha256(row["detail"].encode()).hexdigest(),
            note="Same DUT mismatch/tick/outcome; traceback source line numbers have changed since the old unified build. Original details are not normalized or overwritten."))
    old_reset = cases("vsq-expanded-01")
    resets = []
    for node, row in old_reset.items():
        if row["outcome"] == "FAIL" and "test_reset_aborts_old_owners" in node:
            assert "'before', 'io_empty', 1, 0" in row["detail"] and data[node]["outcome"] == "PASS"
            resets.append(dict(nodeid=node, old_first_assertion=row["detail"].splitlines()[0],
                current_outcome="PASS", historical_detail_SHA256=hashlib.sha256(row["detail"].encode()).hexdigest(),
                classification="VERIFICATION_ERROR_CONFIRMED", reason="The RTL asynchronously clears enqueue/dequeue pointers at reset assertion, before the sampled clock edge. A pre-edge io_empty=0 expectation using old occupied state is invalid.",
                counts_against_current227_failures=False))
    assert len(resets) == 2
    errors = []
    for run, count in ((RUNS[0], 18), (RUNS[1], 6)):
        items = [dict(nodeid=n, failure=r["detail"].splitlines()[0]) for n, r in cases(run).items()
            if r["outcome"] == "FAIL" and r["detail"].startswith("KeyError:")]
        assert len(items) == count
        errors.append(dict(run=run, classification="VERIFICATION_ERROR_CONFIRMED", failing_executions=count,
            nodes=items, reason="New probe accessed unretained constant-ready ports; not a native RTL failure.", counts_against_current227_failures=False))
    return dict(current_boundary_failures=boundary, six_legal_or_reset_controls_pass=True,
        historical_reset_false_positives=resets, new_probe_interface_errors=errors,
        new_probe_error_failing_executions=24, new_probe_error_distinct_nodes=18,
        current227_false_positive_count_not_inferred_from_historical_or_new_probe_errors=True)


def inventory(evidence_rows, domains):
    issue_records = load(ROOT / "manifest/known-issues.json")["issues"]
    explicit = defaultdict(set)
    for issue in issue_records:
        entries = list(issue.get("failure_cases", []))
        if "nodeid" in issue:
            entries.append(issue["nodeid"])
        for item in entries:
            node = item if isinstance(item, str) else item["nodeid"]
            explicit[node.replace(".py::", "::").replace("/", ".")].add(issue["id"])
    named = {
        "test_returned_sid_new_response_cannot_overwrite_old_unconsumed_load": "LQU-SID-001",
        "test_returned_sid_is_reusable_before_old_load_bypass_without_corrupting_it": "LQU-SID-001",
        "test_clean_responses_keep_original_unconsumed_s2_bytes_after_legal_sid_reuse": "LQU-SID-001",
        "test_release_window_through_real_parent_keeps_precise_line": "RAR-REL-001",
        "test_real_cached_rar_release_window_replay_feedback_and_vlq_completion": "RAR-REL-001",
        "test_LDU_RAR_nuke_original_flushAfter_not_C_NK_and_same_slot_new_UID_completes": "RAR-REL-001",
        "test_disabled_s3_feedback_cannot_clear_live_strict_dependency": "LRQ-STRICT-001",
        "test_actual_sq_bitmap_cannot_clear_strict_from_disabled_feedback": "LRQ-STRICT-001",
        "test_full_population_real_ready_bitmap_does_not_replace_strict_execution_wakeup": "LRQ-STRICT-001",
        "test_full_reference_keeps_response_errors_during_wb_stall": "DEQ-WB-001",
        "test_real_parent_cache_error_at_actual_wb_fire": "DEQ-WB-001",
        "test_cache_error_through_real_vsq_identity_at_actual_wb_fire": "DEQ-WB-001",
        "test_actual_cache_wb_fire_keeps_original_fault_despite_backpressure": "DEQ-WB-001",
        "test_serialized_cbo_actual_fault_WB_preserves_original_response_without_younger_dispatch": "DEQ-WB-001",
        "test_real_parent_cross_word_va_alias_never_returns_old_pa_bytes": "FWD-ALIAS-001",
        "test_cross_word_va_alias_latest_pa_bytes_through_true_parent": "FWD-ALIAS-001",
        "test_cross_word_youngest_pa_alias_must_not_return_old_store_bytes": "FWD-ALIAS-001",
        "test_real_parent_cross_word_mask_cannot_name_unwritten_pa_bytes": "FWD-RANGE-001",
        "test_cross_word_store_cannot_supply_unwritten_pa_bytes": "FWD-RANGE-001",
        "test_cross_word_forward_never_invents_unwritten_physical_bytes": "FWD-RANGE-001",
        "test_clipped_dependency_preserves_actual_store_sq_generation": "FWD-SQID-001",
        "test_real_nonzero_sq_head_keeps_data_dependency_full_sq_generation": "FWD-SQID-001",
        "test_real_parent_split_tail_actual_fire_is_not_neighbor_zero": "DEQ-SPLIT-WLINE-001",
        "test_retired_split_then_rob_head_cbo_tail_fire_keeps_ordinary_control": "DEQ-SPLIT-WLINE-001",
        "test_actual_split_tail_wline_belongs_to_ordinary_owner_not_neighbor_cbo": "DEQ-SPLIT-WLINE-001",
        "test_real_vsq_rob_head_zero_must_write_its_own_line_before_wb": "DEQ-ZERO-001",
        "test_zero_actual_wb_and_sq_release_require_own_zero_transfer": "DEQ-ZERO-001",
        "test_serialized_zero_retired_old_sbuffer_still_requires_own_zero16_strict": "DEQ-ZERO-001",
        "test_serialized_zero_retired_old_sbuffer_actual_WB_and_release_protocol_only": "DEQ-ZERO-001",
        "test_completed_special_cannot_release_older_stalled_sbuffer_owner": "DEQ-FINISH-ORDER-001",
        "test_real_psq_special_finish_cannot_release_stalled_older_write": "DEQ-FINISH-ORDER-001",
        "test_actual_special_finish_cannot_release_unconsumed_old_store_prefix": "DEQ-FINISH-ORDER-001",
    }
    datasets = {name: cases(name) for name in (UNIFIED, LATEST)}
    all_failures = sorted(set().union(*({node for node, row in data.items() if row["outcome"] == "FAIL"} for data in datasets.values())))
    assert len(all_failures) == 228
    boundary_nodes = {row["nodeid"]: row for row in domains["current_boundary_failures"]}
    result = []
    for node in all_failures:
        assigned = set(explicit[node])
        function = node.split("::")[1].split("[")[0]
        if function in named:
            assigned.add(named[function])
        nominations = sorted(assigned)
        history = []
        for run, data in datasets.items():
            if node in data and data[node]["outcome"] == "FAIL":
                history.append(dict(run=run, first_failure=data[node]["detail"].splitlines()[0],
                    exception_type=data[node]["detail"].split(":", 1)[0],
                    full_detail_SHA256=hashlib.sha256(data[node]["detail"].encode()).hexdigest()))
        result.append(dict(nodeid=node, histories=history, candidate_families=nominations,
            nomination_basis="Issue-record/test-name mapping is navigation, not an oracle or proof of equivalent histories.",
            family_independent_review_available=[issue for issue in nominations if issue in evidence_rows],
            node_adjudication="PRODUCER_DOMAIN_BOUNDARY" if node in boundary_nodes else "UNRESOLVED_INSTANCE",
            required_next_check="Validate the original producer history and first failed obligation; do not assign a random prefix to a known root solely by test name." if node not in boundary_nodes else "Retain interface FAIL; do not call this a demonstrated normal full-core bug."))
    summary = dict(unique_failed_nodes=228, runs={name: dict(total=len(data), FAIL=sum(r["outcome"] == "FAIL" for r in data.values()),
        failure_SHA256=failure_digest(data)) for name, data in datasets.items()},
        overlap_failed_nodes=195, latest_only_failed_nodes=[row["nodeid"] for row in result if len(row["histories"]) == 1 and row["histories"][0]["run"] == LATEST],
        candidate_family_counts=dict(Counter(issue for row in result for issue in row["candidate_families"])),
        linked_to_four_reviewed_families=sum(bool(row["family_independent_review_available"]) for row in result),
        unassigned_failed_nodes=sum(not row["candidate_families"] for row in result),
        node_level_boundary_adjudicated=3, root_review_is_not_a_blanket_instance_adjudication=True)
    report = dict(format="lsq-fail-review-inventory-v1", summary=summary, rows=result,
        historical_227_and196_results_unchanged=True, no_supplemental_failures_dropped=True)
    write_report(OUT / "failure-inventory-v1.json", report)
    return summary


def unresolved_head_cancel():
    node = "tests.store_queue.test_cancel_capacity::test_real_cancel_capacity_old_bytes_and_every_new_UID_normal_consumption[True]"
    detail = cases(LATEST)[node]["detail"]
    assert detail.startswith("RuntimeError: coroutine raised StopIteration")
    assert 'lsqverify/store_queue/actor.py:234' in detail
    paths = list((ROOT / "results" / LATEST / "cases").rglob("vsq-cancel-capacity-failure.json"))
    assert len(paths) == 1
    path, witness = paths[0], load(paths[0])
    assert witness["tick"] == 932 and witness["physical_base"] == 254 and witness["head_permit_before_redirect"]
    old, new = witness["cancelled_old_owners"], witness["replacement_owners"]
    assert len(old) == len(new) == 64
    observed = []
    for lane in range(2):
        prefix = f"io_writeToSbuffer_req_{lane}_"
        pins = witness["actual_public_Sbuffer"]
        if not pins[prefix + "valid"]:
            continue
        va, pa, mask, data = (pins[prefix + "bits_" + key] for key in ("vaddr", "addr", "mask", "data"))
        candidates = [owner for owner in old if owner["vaddr"] // 16 * 16 == va]
        assert len(candidates) == 1 and not any(owner["vaddr"] // 16 * 16 == va for owner in new)
        owner = candidates[0]
        assert mask == 255 and owner["paddr"] // 16 * 16 == pa
        selected = sum(255 << (8 * b) for b in range(16) if mask >> b & 1)
        assert not (owner["data"] ^ data) & selected
        observed.append(dict(lane=lane, old_UID=owner["uid"], physical_position=owner["position"], actual_VA=va, actual_PA=pa, mask=mask))
    assert observed
    actor = ROOT / "store_queue/actor.py"
    text = actor.read_text().splitlines()
    assert "self.live.values()" in text[233] and "del self.live[self.all[uid].position]" in text[338]
    fifo = ROOT / "rtl/store_queue/EnterSbufferQueue.sv"
    data = fifo.read_text()
    header = data[data.index("module EnterSbufferQueue("):data.index(");", data.index("module EnterSbufferQueue(")) + 2]
    assert not re.search(r"flush|redirect|robIdx|sqIdx", header, re.I)
    assert sha(fifo) == load(fifo.parent / "source.json")["files"][fifo.name]
    return dict(nodeid=node, classification="UNRESOLVED", failure_origin="VERIFICATION_ACTOR_IDENTITY_LOOKUP",
        first_failure=detail.splitlines()[0], full_failure_detail_SHA256=hashlib.sha256(detail.encode()).hexdigest(),
        compact_failure=identity(path), actual_old_owners=observed, actor=identity(actor),
        mechanism="cancel removes old owners from actor.live; subsequent valid Sbuffer data still belongs to an old UID. The next(live-owner) lookup raises StopIteration before an explicit ownership verdict.",
        FIFO_source=identity(fifo), exported_FIFO_has_no_redirect_input=True,
        limits="The old-byte observation is real, but a verification-side lookup crash alone does not decide whether RTL is wrong or head cancellation was illegal after precommit/FIFO acceptance. The compact witness does not reconstruct the earlier FIFO-acceptance tick. Non-IRQ head-self-flush legality and correct irrevocable side-effect accounting remain open. Do not waive this FAIL or silently map it to the replacement owner.")


def audit():
    protected = guard_old()
    runs = audit_runs()
    selected = witnesses()
    semantics = check_semantics(selected)
    sources = fixed_sources()
    lineage = source_lineage()
    domains = domain_and_verification_errors()
    counts = inventory(semantics, domains)
    head = unresolved_head_cancel()
    roots = []
    for issue, explanation, limits in (
        ("LQU-SID-001", "Old returned SID remains enabled in resident LQU entry; another legal response for the reused SID overwrites original data/error.", "Native Uncache allocator joint execution, full LoadUnit and ISA effects are not proved by this probe."),
        ("DEQ-WB-001", "Error latches are cleared in writeback state without waiting for writeBack.fire; accepted response errors disappear under backpressure.", "Confirmed at Deq public interface. Complete Backend arbitration/backpressure reachability remains separate."),
        ("LRQ-STRICT-001", "Unconditional strict(enqIndex):=false in the otherwise arm is indexed by inactive input payload; bitmap readiness then permits original strict owner to replay early.", "The witness observes premature valid, not an unauthorized grant: ready stays low until real pointer release. Full-core consequence is not inferred."),
        ("RAR-REL-001", "Generated release-valid delay is two registers while held address updates on the original valid; previous-cycle association misses and two-cycle-old association appears instead.", "Previous-window miss violates the declared RAR contract. Extra expired nuke alone is conservative replay and is not independently an ISA corruption proof."),
    ):
        roots.append(dict(issue=issue, classification="RTL_INTERFACE_CONFIRMED", explanation=explanation,
            independent_reproduction=semantics[issue], integrated_reachability="Prior parent evidence exists; not independently rerun in this first batch.",
            architecture_consequence="NOT_PROVEN", limits=limits))
    final_guard = guard_old()
    assert final_guard == protected
    first_audit = load(OUT / "first-batch-audit-receipt-v1.json")
    assert first_audit["actual_exitstatus"] == 1
    assert "'docs'" in (OUT / "first-batch-audit-01.log").read_text()
    report = dict(format="lsq-fail-review-first-batch-v1", contract="docs/contracts/fail-review-v1.md",
        inventory=counts, actual_runs=runs, current_distinct_independent_probes=32,
        independent_probe_results={key: value["tests"] for key, value in semantics.items()},
        effective_independent_results=dict(PASS=22, FAIL=10),
        aggregation_scope="Latest valid evidence for each of32distinct small probes across01/02/03, not a new unified regression, not a native coverage OR.",
        roots=roots, domain_and_verification_review=domains, source_evidence=sources, probe_source_lineage=lineage,
        unresolved_required_head_cancel=head,
        first_audit_tool_error=dict(classification="VERIFICATION_ERROR_CONFIRMED_AUDIT_ONLY",
            log=identity(OUT / "first-batch-audit-01.log"), receipt=identity(OUT / "first-batch-audit-receipt-v1.json"),
            reason="Preflight source_summary counts docs/contracts only, grouped under docs. The first checker incorrectly scanned all docs including reports; corrected the comparison scope, without modifying any old artifact or rerunning a DUT."),
        old_evidence_protection=protected,
        verification=dict(all_selected_witness_obligations_recomputed_from_public_events=True,
            all_four_native_reproductions_and_necessary_condition_controls_checked=True,
            fixed_commit_Scala_utility_gitlink_and_generated_RTL_checked=True,
            old_source_and141_artifacts_unchanged=True, no_RTL_model_fixture_or_old_test_changed=True,
            no_skip_xfail_or_DUT_outcome_suppression=True, no_full_regression_rerun=True),
        limits="First four root families and three domain-boundary nodes reviewed. Most original node histories remain UNRESOLVED_INSTANCE. Historical reset false positives and24new-probe KeyError executions are not deducted from current227or196. Native rawline/toggle/branch coverage from these probes is not an acceptance metric and is not merged into earlier runs.")
    write_report(OUT / "first-batch-review-v1.json", report)
    queue = dict(format="lsq-fail-review-next-queue-v1", inventory=identity(OUT / "failure-inventory-v1.json"),
        items=[
            dict(priority=1, families=["FWD-ALIAS-001", "FWD-RANGE-001", "FWD-SQID-001"],
                scope="52 nominated nodes; independently check byte provenance/SQ epoch and separate the2arbitrary-hole-mask interface cases. Do not infer parent legality from leaf data equality."),
            dict(priority=2, families=["DEQ-SPLIT-WLINE-001", "DEQ-ZERO-001", "DEQ-FINISH-ORDER-001"],
                scope="33 nominated nodes; reconstruct original owner of each actual Sbuffer transfer and contiguous completion prefix, then prove special/CBO head permission."),
            dict(priority=3, families=["LSQ-BUS-OWNERSHIP-001"],
                scope="4 nominated nodes; distinguish premature valid from actual fire, and externally returned Load identity from outstanding serialized Store identity."),
            dict(priority=4, families=["UNASSIGNED_MIXED_AND_HEAD_CANCEL"],
                scope="63 unassigned nodes. Minimize by first violating public event, not by seed/name. Preserve all original UID and external-response obligations. Required head-cancel crash receives a separate legality/accounting review.")],
        do_not_auto_close_same_message_or_same_seed_as_same_bug=True,
        do_not_mark_unresolved_as_false_positive=True, full_regression_not_required_before_minimal_reproduction=True)
    write_report(OUT / "next-review-queue-v1.json", queue)
    print(json.dumps(dict(inventory=counts, independent_results=report["effective_independent_results"],
        roots=[dict(issue=r["issue"], classification=r["classification"], tests=semantics[r["issue"]]["tests"]) for r in roots],
        boundaries=3, old_protected_artifacts=protected["protected_artifacts"], verification=report["verification"]), indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    audit()
