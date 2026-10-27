"""Read-only, bounded proofs for redundant generated TAGE copy paths.

Run ``python3 bpuverify/tage_coverage_audit.py`` after a full coverage refresh.
This does not remove rows from the native denominator or prove that the other
rows are reachable. Source guards and their exact lexical neighborhood are
checked before applying the two-state Boolean truth-table proof.
"""

from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

from bpuverify.tage.coverage.guard_catalog import counter_blocks


ROOT = Path(__file__).resolve().parents[3]
SOURCE = "rtl/tage/WriteBuffer.sv"


def _truth_table(kind: str, *, keep_priority: bool = True) -> list[dict[str, bool]]:
    witnesses = []
    for values in itertools.product((False, True), repeat=4):
        hit, selected, written, equal = values
        priority = hit and selected
        path = (not priority if keep_priority else True) and hit
        if kind == "dirty_copy":
            path = path and selected
        elif kind == "clean_copy":
            path = path and not (not written or equal or not selected)
        else:
            raise ValueError(kind)
        if path:
            witnesses.append(dict(zip(("hit", "selected", "written", "equal"), values)))
    return witnesses


def audit(native=None) -> dict[str, object]:
    native = json.loads((ROOT / "results/rtl-line-coverage.json").read_text()) if native is None else native
    prior = dict(blocks=counter_blocks())
    original = (ROOT / SOURCE).read_text().splitlines()
    lines = [line.split("//", 1)[0].strip() for line in original]

    def expect(number: int, text: str) -> None:
        assert lines[number - 1] == text, (number, text, lines[number - 1])

    def definition(name: str, expression: str) -> int:
        matches = [i + 1 for i, line in enumerate(lines)
                   if re.fullmatch(re.escape(name) + r"\s*=\s*" + re.escape(expression) + ";", line)]
        assert len(matches) == 1, (name, expression, matches)
        return matches[0]

    blocks = []

    def prove(*, row, entry, port, kind, priority_line, priority_guard, selected,
              hit_line, copy_guard_line, body_first, body_last, hit):
        expect(priority_line, f"if ({priority_guard}) begin")
        expect(hit_line, f"else if ({hit}) begin")
        priority_definition = definition(priority_guard, f"{hit} & {selected}")
        if kind == "dirty_copy":
            expect(hit_line + 1, f"if (hitNotWritten{'_1' if port == 1 else ''}) begin")
            expect(copy_guard_line, f"if ({selected})" + (" begin" if row == 0 else ""))
            expect(body_last + 1, "end")
        else:
            written = f"hitWritten{'_1' if port == 1 else ''}"
            compare = "_GEN_119" if port == 1 else "_GEN_44"
            gate = f"~{written} | {compare} | ~{selected}"
            if row == 0:
                expect(copy_guard_line, f"else if ({gate}) begin")
                expect(body_first - 1, "else begin")
                expect(body_last + 1, "end")
            else:
                guard = f"_GEN_{54 + entry}"
                definition(guard, gate)
                expect(copy_guard_line, f"else if ({guard}) begin")
                expect(copy_guard_line + 1, "end")
                expect(body_first - 1, "else")
        body = lines[body_first - 1:body_last]
        suffix = f"io_write_{port}_bits_"
        assert all(line.startswith(f"entries_{row}_{entry}_") and " <= " + suffix in line
                   for line in body), (body_first, body)
        if row == 0:
            assert [line.split(" <= ")[0] for line in body] == [
                f"entries_{row}_{entry}_setIdx", f"entries_{row}_{entry}_entry_valid",
                f"entries_{row}_{entry}_entry_tag", f"entries_{row}_{entry}_entry_takenCtr_value",
            ]
        else:
            assert len(body) == 1 and "entry_takenCtr_value" in body[0]
        assert not _truth_table(kind)
        control = _truth_table(kind, keep_priority=False)
        assert control, ("Removing the priority exclusion must invalidate the proof", kind)
        blocks.append({
            "file": SOURCE, "row": row, "entry": entry, "write_port": port,
            "kind": kind, "priority_guard_line": priority_line,
            "priority_definition_line": priority_definition,
            "priority_definition": f"{priority_guard} = {hit} & {selected}",
            "later_hit_guard_line": hit_line, "copy_guard_line": copy_guard_line,
            "body_first_line": body_first, "body_last_line": body_last,
            "path_constraint": "!(H && S) && H && S" if kind == "dirty_copy" else
                               "!(H && S) && H && !(!W || C || !S)",
            "two_state_valuations_checked": 16, "satisfying_valuations": 0,
            "negative_control_without_priority_witness": control[0],
        })

    for entry in range(4):
        offset = 95 * entry
        selected = ("_GEN_97", "_GEN_99", "_GEN_101", "_GEN_102")[entry]
        common = dict(row=0, entry=entry, port=1, hit="hit_1", selected=selected,
                      priority_guard=f"_GEN_{129 + entry}",
                      priority_line=804 + offset, hit_line=817 + offset)
        prove(**common, kind="dirty_copy", copy_guard_line=819 + offset,
              body_first=820 + offset, body_last=823 + offset)
        prove(**common, kind="clean_copy", copy_guard_line=849 + offset,
              body_first=872 + offset, body_last=875 + offset)
        for base, stride in ((1197, 34), (1424, 20)):
            start = base + stride * entry
            common = dict(row=1, entry=entry, port=0, hit="hit", selected=f"_GEN_{36 + entry}",
                          priority_guard=f"_GEN_{66 + entry}",
                          priority_line=start, hit_line=start + 10)
            prove(**common, kind="dirty_copy", copy_guard_line=start + 12,
                  body_first=start + 13, body_last=start + 13)
            prove(**common, kind="clean_copy", copy_guard_line=start + 15,
                  body_first=start + 18, body_last=start + 18)

    prior_rows = {(b["file"], n) for b in prior["blocks"]
                  for n in range(b["body_first_line"], b["body_last_line"] + 1)}
    added = {(b["file"], n) for b in blocks
             for n in range(b["body_first_line"], b["body_last_line"] + 1)}
    raw = {(g["file"], g["line"]) for g in native["dut"]["tage"]["uncovered_rtl_source_lines"]}
    assert len(blocks) == 24 and len(added) == 48 and len(prior_rows) == 40
    assert not (added & prior_rows) and (added | prior_rows) <= raw
    return {
        "format": "bpu-generated-rtl-priority-unreachable-audit", "version": 1,
        "generated_at": native["generated_at"], "dut": "tage",
        "proof_scope": "Locally contradictory priority exclusions, not whole-RTL formal reachability",
        "native_line_coverage": native["dut"]["tage"]["source_lines"],
        "native_denominator_unchanged": True, "raw_uncovered_source_lines": len(raw),
        "prior_proof": "bpuverify/tage/coverage/guard_catalog.py",
        "prior_classified_assignment_lines": len(prior_rows),
        "additional_classified_assignment_lines": len(added),
        "combined_classified_assignment_lines": len(added | prior_rows),
        "not_classified_remaining_source_lines": len(raw - added - prior_rows),
        "classification_does_not_prove_other_lines_reachable": True, "blocks": blocks,
    }


def audit_key_copies(native=None) -> dict[str, object]:
    """Extend the priority proof to row1's separate set/valid/tag copies.

    Unlike the counter body, these three fields are emitted in a different
    lexical block. Check that block itself instead of extending a line range
    or assuming that a fixed input port implies a fixed hit row.
    """

    native = json.loads((ROOT / "results/rtl-line-coverage.json").read_text()) if native is None else native
    priority = audit(native)
    prior = dict(blocks=counter_blocks())
    lines = [line.split("//", 1)[0].strip()
             for line in (ROOT / SOURCE).read_text().splitlines()]

    def expect(number: int, text: str) -> None:
        assert lines[number - 1] == text, (number, text, lines[number - 1])

    def definition(name: str, expression: str) -> int:
        matches = [i + 1 for i, line in enumerate(lines)
                   if re.fullmatch(re.escape(name) + r"\s*=\s*" + re.escape(expression) + ";", line)]
        assert len(matches) == 1, (name, expression, matches)
        return matches[0]

    blocks = []
    for entry in range(4):
        start = 1535 + 28 * entry
        selected, guard, clean = f"_GEN_{36 + entry}", f"_GEN_{66 + entry}", f"_GEN_{54 + entry}"
        priority_definition = definition(guard, f"hit & {selected}")
        clean_definition = definition(clean, f"~hitWritten | _GEN_44 | ~{selected}")
        expect(start, f"if ({guard}) begin")
        expect(start + 4, "end")
        expect(start + 5, "else if (hit) begin")
        expect(start + 6, "if (hitNotWritten) begin")
        expect(start + 7, f"if ({selected}) begin")
        expect(start + 11, "end")
        expect(start + 12, "end")
        expect(start + 13, f"else if ({clean}) begin")
        expect(start + 14, "end")
        expect(start + 15, "else begin")
        expect(start + 19, "end")
        expect(start + 20, "end")
        expect(start + 21, "end")
        for kind, offset in (("dirty_copy", 8), ("clean_copy", 16)):
            first = start + offset
            for index, field in enumerate(("setIdx", "entry_valid", "entry_tag")):
                expect(first + index, f"entries_1_{entry}_{field} <= io_write_0_bits_{field};")
            assert not _truth_table(kind)
            witnesses = _truth_table(kind, keep_priority=False)
            assert witnesses
            blocks.append({
                "file": SOURCE, "row": 1, "entry": entry, "write_port": 0, "kind": kind,
                "priority_guard_line": start, "priority_definition_line": priority_definition,
                "priority_definition": f"{guard} = hit & {selected}",
                "later_hit_guard_line": start + 5,
                "copy_guard_line": start + (7 if kind == "dirty_copy" else 13),
                "clean_definition_line": clean_definition,
                "clean_definition": f"{clean} = ~hitWritten | _GEN_44 | ~{selected}",
                "body_first_line": first, "body_last_line": first + 2,
                "path_constraint": "!(H && S) && H && S" if kind == "dirty_copy" else
                                   "!(H && S) && H && !(!W || C || !S)",
                "two_state_valuations_checked": 16, "satisfying_valuations": 0,
                "negative_control_without_priority_witness": witnesses[0],
            })
    older = {(b["file"], n) for b in prior["blocks"] + priority["blocks"]
             for n in range(b["body_first_line"], b["body_last_line"] + 1)}
    added = {(b["file"], n) for b in blocks
             for n in range(b["body_first_line"], b["body_last_line"] + 1)}
    raw = {(g["file"], g["line"]) for g in native["dut"]["tage"]["uncovered_rtl_source_lines"]}
    assert len(blocks) == 8 and len(older) == 88 and len(added) == 24
    assert not (older & added) and (older | added) <= raw
    return {
        "format": "bpu-generated-rtl-key-copy-priority-audit", "version": 1,
        "generated_at": native["generated_at"], "dut": "tage",
        "proof_scope": "Exact local two-state priority contradictions, not full RTL reachability",
        "native_line_coverage": native["dut"]["tage"]["source_lines"],
        "native_denominator_unchanged": True, "raw_uncovered_source_lines": len(raw),
        "prior_classified_assignment_lines": len(older),
        "additional_classified_assignment_lines": len(added),
        "combined_classified_assignment_lines": len(older | added),
        "not_classified_remaining_source_lines": len(raw - older - added),
        "classification_does_not_prove_other_lines_reachable": True, "blocks": blocks,
    }


def source_claims(native):
    """Revalidate counter bodies, copy bodies and eight else-block heads.

    Claims are separate from native-point association. The diagnostic caller
    must verify every l/arm/S producer before interpreting them as DA gaps.
    """
    from bpuverify.common.coverage.local_guards import Source, claim

    priority = audit(native)
    keys = audit_key_copies(native)
    prior = dict(blocks=counter_blocks())
    source,claims = Source(SOURCE),[]
    for block in prior['blocks']:
        outer,inner,otherwise = block['outer_guard_line'],block['inner_hit_guard_line'],block['inner_else_line']
        hit = block['definition'].split('&',1)[0].strip()
        assert hit in ('hit','hit_1')
        source.definition(block['guard'],block['definition'])
        source.expect(outer,f"if ({block['guard']}) begin")
        source.expect(inner,f'if ({hit}) begin')
        assert source.closing(inner)==otherwise-1
        assert source.lines[otherwise-1] in ('else','else begin')
        first,last = block['body_first_line'],block['body_last_line']
        assert first==otherwise+1
        source.encloses(outer,first,last)
        body = ''.join(source.lines[first-1:last])
        assert re.sub(r'\s+','',body)==re.sub(r'\s+','',block['assignment'])
        assert not any(value and not value for value in (False,True))
        claims.append(claim(SOURCE,first,last,inner,'else','outer-hit-and-inner-not-hit-counter'))
    for block in priority['blocks']+keys['blocks']:
        first,last = block['body_first_line'],block['body_last_line']
        # Existing proof checks this exact lexical else and enclosing guards.
        if block['kind']=='clean_copy' and source.lines[first-2]=='else begin':
            first -= 1
        claims.append(claim(SOURCE,first,last,block['copy_guard_line'],
            'if' if block['kind']=='dirty_copy' else 'else','priority-excluded-'+block['kind']))
    assert sum(item['last']-item['first']+1 for item in claims)==120
    return claims,[dict(file=SOURCE,sha256=source.sha256)]


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
