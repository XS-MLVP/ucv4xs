#!/usr/bin/env python3
"""Bound the two pinned VSQ count cones without driving illegal encodings."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from audit_coverage_points_v1 import records, sha256_file
from audit_evidence_io import write_report
from audit_gap_closure_v1 import native
from audit_vsq_recovery_boundaries_v1 import SOURCES, source_proof

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class LinearValue:
    width: int
    maximum: int
    coefficients: Counter


class ZeroExtendedSum:
    """A deliberately narrow parser: zeros, vars, +, concat and sized casts.

    Every addition and sized cast must fit without truncation. Concat high
    fields must be exactly zero. Thus an affine sum over bounded nonnegative
    variables is preserved, not merely sampled on a few input vectors.
    """

    def __init__(self, text, variables):
        self.tokens = re.findall(r"\d+'h[0-9a-fA-F]+|\d+'|[A-Za-z_]\w*|[{}(),+]", text)
        assert "".join(self.tokens) == re.sub(r"\s+", "", text), "unsupported SV token"
        self.index, self.variables, self.checked_nodes = 0, variables, 0

    def take(self, expected=None):
        token = self.tokens[self.index]
        self.index += 1
        assert expected is None or token == expected, (token, expected)
        return token

    def peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def expression(self):
        value = self.atom()
        while self.peek() == "+":
            self.take("+")
            other = self.atom()
            width, maximum = max(value.width, other.width), value.maximum + other.maximum
            assert maximum < 1 << width, "addition can overflow at its own width"
            value = LinearValue(width, maximum, value.coefficients + other.coefficients)
            self.checked_nodes += 1
        return value

    def atom(self):
        token = self.take()
        self.checked_nodes += 1
        if re.fullmatch(r"\d+'h[0-9a-fA-F]+", token):
            width, number = token.split("'h")
            assert int(number, 16) == 0
            return LinearValue(int(width), 0, Counter())
        if re.fullmatch(r"\d+'", token):
            self.take("("); value = self.expression(); self.take(")")
            width = int(token[:-1])
            assert value.maximum < 1 << width, "cast can truncate significant bits"
            return LinearValue(width, value.maximum, value.coefficients)
        if token == "(":
            value = self.expression(); self.take(")")
            return value
        if token == "{":
            pieces = [self.expression()]
            while self.peek() == ",":
                self.take(","); pieces.append(self.expression())
            self.take("}")
            assert len(pieces) >= 2 and all(piece.maximum == 0 for piece in pieces[:-1])
            return LinearValue(sum(piece.width for piece in pieces), pieces[-1].maximum, pieces[-1].coefficients)
        assert token in self.variables, token
        width, maximum = self.variables[token]
        return LinearValue(width, maximum, Counter({token: 1}))

    def parse(self):
        result = self.expression()
        assert self.peek() is None
        return result


def cones(dut):
    pinned = source_proof(dut)
    source = (ROOT / SOURCES[dut]).read_text()
    cancel = re.search(r"wire\s+\[7:0\]\s+cancelCount\s*=\s*([^;]+);", source)
    assert cancel
    variables = {f"needCancelReg_{i}": (1, 1) for i in range(128)}
    parser = ZeroExtendedSum(cancel[1], variables)
    result = parser.parse()
    assert result.width == 8 and result.maximum == 128 and result.coefficients == Counter({v: 1 for v in variables})
    cancel_proof = dict(source=SOURCES[dut], source_SHA256=pinned["source_SHA256"], declaration_line=4597,
        expression_SHA256=hashlib.sha256(cancel[1].encode()).hexdigest(), width=result.width,
        exact_boolean_popcount_terms=len(result.coefficients), hardware_maximum=result.maximum,
        checked_nontruncating_expression_nodes=parser.checked_nodes,
        candidate_counts_for_high_bits=[dict(cancelled_virtual_uops=n, target_bit=bit) for bit, n in ((4, 16), (5, 32), (6, 64), (7, 128))],
        limits="Count is over virtual uops, not physical flows.128-uop leaf stimulus requires a compact0/1-flow legal window; ordinary parent physical consumption and actual ROB occupancy must be checked separately. No case was run by this static audit.")
    assert re.search(r"wire\s+\[127:0\]\[4:0\]\s+_GEN_43\s*=", source)
    writes = list(re.finditer(r"\bretireReqNumReg\s*<=\s*([^;]+);", source))
    assert len(writes) == 1
    expression = writes[0][1]
    selections = []
    for lane in range(8):
        pattern = rf"retireVec_{lane}_REG\s*\?\s*\{{3'h0,\s*_GEN_43\[deqPtrVec_{lane}_value\]\}}\s*:\s*8'h0"
        expression, count = re.subn(pattern, f"flow_{lane}", expression)
        assert count == 1
        selections.append(dict(lane=lane, selected_input_bits=5, gated_term_bits=8, hardware_maximum=31))
    parser = ZeroExtendedSum(expression, {f"flow_{lane}": (8, 31) for lane in range(8)})
    result = parser.parse()
    assert result.width == 11 and result.maximum == 248 and result.coefficients == Counter({f"flow_{i}": 1 for i in range(8)})
    initial = re.findall(r"\bretireReqNumReg\s*=(?!=)\s*([^;]+);", source)
    assert initial == ["_RANDOM[7'h7E][18:8]"]
    write_line = source[:writes[0].start()].count("\n") + 1
    assert write_line == 14292
    return dict(dut=dut, cancel_count=cancel_proof,
        retirement_sum=dict(source=SOURCES[dut], source_SHA256=pinned["source_SHA256"], declaration_line=5397,
            write_range=[14291, 14313], expression_SHA256=hashlib.sha256(writes[0][1].encode()).hexdigest(),
            width=11, selected_terms=selections, hardware_maximum_per_known_write=248,
            legal_contract_max_flow_per_uop=16, legal_contract_sum_bound=128,
            constant_zero_bits_after_known_write=[8, 9, 10], unreset_random_initial_write=True,
            checked_nontruncating_expression_nodes=parser.checked_nodes,
            limits="The register is not reset; random/uninitialized startup payload and transitions into the first known value are not excluded. Bits8..10 are zero on every clocked write even for31-flow raw input, and remain zero after a known write. This is not a claim that raw toggle points for those bits are globally unreachable or may be removed. Legal per-uop bound16 is narrower than the5-bit hardware interface."))


def audit(name):
    rows = []
    for dut in SOURCES:
        proof = cones(dut)
        meta, dat = native(name, dut)
        assert sha256_file(dat) == meta["artifact"]["sha256"]
        selected = [p for p in records(dat) if p["t"] == "toggle" and p["f"] == str(ROOT / SOURCES[dut]) and
                    (p["o"].startswith("cancelCount[") or p["o"].startswith("retireReqNumReg["))]
        assert len(selected) == 38
        proof.update(native_build_id=meta["artifact"]["build"]["build_id"], coverage_dat_SHA256=meta["artifact"]["sha256"],
                     retained_missing_points=[dict(source_line=int(p["l"]), point=p["o"], hierarchy=p["h"], hit=p["hit"]) for p in selected if p["hit"] <= 0])
        rows.append(proof)
    report = dict(format="lsq-vsq-count-domain-audit-v1", run=name, rows=rows,
        verification=dict(pinned_sources_checked=True, nontruncating_zero_extended_sum_cones_checked=True,
            all128_boolean_cancel_terms_exactly_once=True, eight5bit_gated_retire_terms_exactly_once=True,
            no_startup_or_unreset_register_waiver=True, native_missing_points_and_denominators_retained=True),
        status="NEXT_GAP_TRIAGE_NOT_DYNAMIC_COVERAGE_GAIN",
        limits="Independent static arithmetic-cone audit and actual native missing-point inventory only. No new stimulus was run, no old point was deleted/reclassified globally, and no parent/full-goal completion is claimed.")
    write_report(ROOT / "results" / name / "vsq-count-domain-audit-v1.json", report)
    print(json.dumps(dict(status=report["status"], rows=[dict(dut=r["dut"],cancel_max=r["cancel_count"]["hardware_maximum"],retire_hardware_write_max=r["retirement_sum"]["hardware_maximum_per_known_write"],remaining_points=len(r["retained_missing_points"])) for r in rows],verification=report["verification"]),indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
