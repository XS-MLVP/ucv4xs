#!/usr/bin/env python3
"""Exact post-reset state3 proof, not a waiver for the release-wait branch."""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
from itertools import product
import json
from pathlib import Path
import re

from audit_coverage_points_v1 import records, sha256_file
from audit_evidence_io import write_report
from audit_gap_closure_v1 import digest_keys, native, point_key
from audit_initial_branch_boundaries_v1 import initial_region

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "virtual_store_queue": "dut/virtual_store_queue/VirtualStoreQueueDut.v",
    "store_queue": "rtl/store_queue/VirtualStoreQueue.sv",
    "lsq_wrapper": "rtl/lsq_wrapper/VirtualStoreQueue.sv",
}
PINNED_SHA = "61685efc3ab12cba8d0695f23d033929b8ead3a30688d71dd51ecf2644bda822"


@lru_cache(maxsize=None)
def source_proof(dut):
    path = ROOT / SOURCES[dut]
    source = path.read_text()
    lines = source.splitlines()
    assert sha256_file(path) == PINNED_SHA
    pinned = json.loads((ROOT / "rtl" / dut / "source.json").read_text())["files"]
    assert pinned["VirtualStoreQueue.sv"] == PINNED_SHA
    assert len(re.findall(r"\breg\s+\[1:0\]\s+state\s*;", source)) == 1
    clocked = [(source[:m.start()].count("\n") + 1, m[1].strip())
               for m in re.finditer(r"\bstate\s*<=\s*([^;]+);", source)]
    assert clocked == [(14578, "2'h0"), (15851, "2'h2"), (15854, "2'h0"), (15857, "2'h1")]
    blocking = [(source[:m.start()].count("\n") + 1, m[1].strip())
                for m in re.finditer(r"\bstate\s*=(?!=)\s*([^;]+);", source)]
    assert blocking == [(17131, "_RANDOM[7'h70][10:9]"), (17463, "2'h0")]
    assert lines[14412].strip() == "always @(posedge clock or posedge reset) begin"
    assert lines[14413].strip() == "if (reset) begin"
    assert lines[14724].strip() == "else begin"
    assert lines[16057].strip() == "end // always @(posedge, posedge)"
    expected = """if (|state) begin
        if (state == 2'h1) begin
          if (~headIsRetired)
            state <= 2'h2;
        end
        else if (state == 2'h2)
          state <= 2'h0;
      end
      else if (io_redirect_valid & headIsRetired)
        state <= 2'h1;"""
    region = "\n".join(lines[15847:15857]).strip()
    assert region == expected
    initialization = [dict(line=line, rhs=rhs, scope=initial_region(str(path), line)) for line, rhs in blocking]
    assert all(item["scope"] is not None for item in initialization)
    return dict(source=SOURCES[dut], source_SHA256=PINNED_SHA, state_width=2, declaration_line=1215,
                clock_process_start=14413, clock_process_end=16058,
                asynchronous_reset_predicate_line=14414, reset_assignment_line=14578, reset_value=0,
                all_clocked_writes=[dict(line=line, rhs=rhs) for line, rhs in clocked],
                nonclocked_writes=initialization, next_state_predicate_range=[15848, 15857],
                next_state_predicate_SHA256=hashlib.sha256((region + "\n").encode()).hexdigest())


def state3_boundary(dut, point):
    if dut not in SOURCES or point.get("t") != "branch" or int(point["l"]) != 15853 or point.get("o") != "else":
        return None
    if Path(point["f"]).resolve() != ROOT / SOURCES[dut]:
        return None
    return source_proof(dut)


def induction():
    # Exact translation of the verified 10-line control region. headIsRetired
    # and redirect are arbitrary booleans, not constrained by a queue model.
    truth = []
    for state, reset, redirect, head in product(range(4), range(2), range(2), range(2)):
        next_state = 0 if reset else (2 if not head else 1) if state == 1 else (
            0 if state == 2 else state) if state != 0 else 1 if redirect and head else 0
        truth.append((state, reset, redirect, head, next_state))
    reachable = {0}
    while True:
        enlarged = reachable | {row[4] for row in truth if row[0] in reachable}
        if enlarged == reachable:
            break
        reachable = enlarged
    excluded_arm = {state for state in range(4) if state != 0 and state != 1 and state != 2}
    assert reachable == {0, 1, 2} and excluded_arm == {3} and not reachable & excluded_arm
    assert all(row[4] in reachable for row in truth if row[0] in reachable)
    return dict(reset_base_case=0, inputs="arbitrary reset/redirect/headIsRetired booleans",
                exhaustive_control_rows=len(truth), control_truth_table_SHA256=digest_keys(set(truth)),
                next_values_by_state={str(state): sorted({row[4] for row in truth if row[0] == state}) for state in range(4)},
                post_reset_reachable_states=sorted(reachable), missing_else_predicate="state != 0 && state != 1 && state != 2",
                codes_satisfying_missing_else=sorted(excluded_arm), post_reset_missing_else_unreachable=True)


def audit(name):
    proof = induction()
    proven, open_wait = [], []
    for dut in SOURCES:
        meta, dat = native(name, dut)
        assert sha256_file(dat) == meta["artifact"]["sha256"]
        points = [p for p in records(dat) if p["t"] == "branch" and p["f"] == str(ROOT / SOURCES[dut])]
        boundary = [p for p in points if state3_boundary(dut, p)]
        waits = [p for p in points if p["l"] == "15850" and p["o"] == "else"]
        assert len(boundary) == len(waits) == 1 and boundary[0]["hit"] == waits[0]["hit"] == 0
        proven.append(dict(dut=dut, build_id=meta["artifact"]["build"]["build_id"], **source_proof(dut),
            coverage_dat_SHA256=sha256_file(dat), source_line=15853, point="else", hierarchy=boundary[0]["h"],
            point_identity_SHA256=digest_keys({point_key(boundary[0])}), hit=0,
            classification="unreachable_or_dont_care", boundary="post_reset_unreachable_state3",
            reason="All state writes and the complete control predicate were checked against the pinned source. Reset sets0; every possible clocked transition from0/1/2 stays in0/1/2. This branch else requires state3. Initialization random states before reset and external fault injection are outside this proof."))
        open_wait.append(dict(dut=dut, source=SOURCES[dut], source_line=15850, point="else", hierarchy=waits[0]["h"],
                              hit=0, classification="existing_feature_missing_case", boundary="release_wait_not_proven_unreachable",
                              reason="This predicate is state1 && headIsRetired and is not excluded by the state encoding proof. Legal timing complements and the remaining exact cone/producer proof must be evaluated separately."))
    report = dict(format="lsq-vsq-recovery-boundaries-v1", run=name, contract="docs/contracts/vsq-release-walk.md",
                  induction=proof, proven_points=proven, proven_post_reset_state3_points=len(proven), open_release_wait_points=open_wait,
                  verification=dict(exact_pinned_source_and_all_state_writes_checked=True, asynchronous_reset_base_case_checked=True,
                      arbitrary_boolean_next_state_closure_checked=True, missing_else_is_exactly_state3=True,
                      every_nonclocked_write_confined_to_initialization=True, all_three_native_points_retained_unhit=True,
                      release_wait_not_waived=True),
                  limits="Static post-reset boundary evidence only, not native coverage gain. Original source/point identities, all branch denominators, raw dat and historical failures remain unchanged. Does not prove the separate release-wait arm unreachable, nor any no-reset/startup/fault-injection/other-configuration behavior.")
    write_report(ROOT / "results" / name / "vsq-recovery-boundary-audit-v1.json", report)
    print(json.dumps({key: value for key, value in report.items() if key not in ("proven_points", "open_release_wait_points")}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
