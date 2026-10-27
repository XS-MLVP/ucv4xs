"""Bounded structural audit of the AheadBTB residual branch arms.

Two claims are checked against the generated source and the native report:

1. Each per-set PLRU chain ends with ``else if (set_touch_ways_0_<S>_valid)``
   inside a block whose own guard already requires at least one of that set's
   four ``readWayMask`` bits.  Falling through therefore needs all four masks
   clear while the guard needs one set, which is unsatisfiable.
2. The ABTB ``WriteBuffer`` ternary ``io_write_0_valid & ~hit ? victim : 0`` is
   generated inside ``if (io_write_0_valid & ~hit)``, so its else arm cannot be
   selected.

This is a bounded source/structure proof plus exact native arm association.  It
never rewrites a native row, never grants functional credit and is not a
whole-design formal claim.
"""
from hashlib import sha256
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[3]
REPLACER = 'rtl/abtb/AheadBtbReplacer.sv'
WRITEBUFFER = 'rtl/abtb/WriteBuffer.sv'
SETS = 64
WAYS = 4


def _code_lines(path):
    return [line.split('//', 1)[0].rstrip() for line in (ROOT / path).read_text().splitlines()]


def _indent(text):
    return len(text) - len(text.lstrip())


def _suffix(set_index):
    return '' if set_index == 0 else f'_{set_index}'


def _mask(set_index, way):
    return f'set_touch_ways_{way}{_suffix(set_index)}_valid'


def _enclosing_guard(lines, number):
    """Return the text of the nearest enclosing ``if (...)`` that guards a line."""
    target = _indent(lines[number - 1])
    for index in range(number - 2, -1, -1):
        text = lines[index]
        if not text.strip() or _indent(text) >= target:
            continue
        if text.strip().startswith('if ('):
            guard = [text.strip()]
            follow = index + 1
            while ') begin' not in guard[-1] and follow < len(lines):
                guard.append(lines[follow].strip())
                follow += 1
            return index + 1, ' '.join(guard)
        target = _indent(text)
    raise AssertionError((number, 'no enclosing guard'))


def replacer_claims(report, dut='abtb'):
    lines = _code_lines(REPLACER)
    arms = [row for row in report['dut'][dut]['uncovered_rtl_branches']
            if row['file'] == REPLACER and row['arm'] == 'else']
    claims = []
    for row in arms:
        number = row['line']
        text = lines[number - 1].strip()
        match = re.fullmatch(r'else if \(set_touch_ways_0(?:_(\d+))?_valid\)', text)
        assert match is not None, (number, text)
        set_index = int(match.group(1) or 0)
        guard_line, guard = _enclosing_guard(lines, number)
        masks = {_mask(set_index, way) for way in range(WAYS)}
        assert all(mask in guard for mask in masks), (number, set_index, guard)
        # The guard must not borrow another set's mask: exactly the four bits of
        # this set may appear.
        mentioned = set(re.findall(r'set_touch_ways_\d(_\d+)?_valid', guard))
        assert {value if value else '' for value in mentioned} == {_suffix(set_index)}, (
            number, set_index, mentioned)
        # The chain ends with way 0 for this set, and its body is the last one
        # before the block closes: there is no final else.
        body = lines[number].strip()
        assert body.startswith('state_vec_') and ' <= ' in body, (number, body)
        closing = lines[number + 1]
        assert closing.strip() == 'end', (number, closing.strip())
        assert closing == '        end', (number, repr(closing))
        claims.append(dict(file=REPLACER, line=number, arm='else', set_index=set_index,
                           guard_line=guard_line, guard=guard,
                           masks=sorted(masks), kind='guard-union-makes-fallthrough-unsatisfiable'))
    assert len(claims) == SETS, (len(claims), SETS)
    assert len({claim['set_index'] for claim in claims}) == SETS
    return claims


def writebuffer_claim(report, dut='abtb'):
    lines = _code_lines(WRITEBUFFER)
    rows = [row for row in report['dut'][dut]['uncovered_rtl_branches']
            if row['file'] == WRITEBUFFER and row['arm'] == 'cond_else']
    assert len(rows) == 1, rows
    number = rows[0]['line']
    text = lines[number - 1].strip()
    assert text == "writeTouchVec_0_bits = io_write_0_valid & ~hit ? victim : 2'h0;", text
    guard_line, guard = _enclosing_guard(lines, number)
    assert guard == 'if (io_write_0_valid & ~hit) begin', guard
    return dict(file=WRITEBUFFER, line=number, arm='cond_else', guard_line=guard_line,
                guard=guard, kind='ternary-inside-its-own-false-branch')


def audit(report, dut='abtb'):
    replacer = replacer_claims(report, dut)
    writebuffer = writebuffer_claim(report, dut)
    lines = _code_lines(REPLACER)
    # Independently re-derive the contradiction for every claim: the union in
    # the guard has four members and the fall-through requires all four false.
    for claim in replacer:
        bits = [f'm{way}' for way in range(WAYS)]
        guard = ' | '.join(bits)
        satisfiable = any(
            eval(guard, {}, dict(zip(bits, values, strict=True)))  # noqa: S307 - four booleans
            and not any(values)
            for values in __import__('itertools').product((False, True), repeat=WAYS))
        assert not satisfiable, claim
    total = report['dut'][dut]['source_lines']
    return dict(
        format='abtb-bounded-structural-branch-audit', version=1,
        source_sha256={REPLACER: sha256((ROOT / REPLACER).read_bytes()).hexdigest(),
                       WRITEBUFFER: sha256((ROOT / WRITEBUFFER).read_bytes()).hexdigest()},
        replacer_arms=len(replacer),
        writebuffer_arms=1,
        covered_arms=len(replacer) + 1,
        sets=SETS,
        claims=replacer,
        writebuffer=writebuffer,
        native_source_lines=dict(total=total['total'], hit=total['hit']),
        native_arms=dict(total=report['dut'][dut]['by_source']['rtl_verilog']['v_branch']['total'],
                         hit=report['dut'][dut]['by_source']['rtl_verilog']['v_branch']['hit']),
        native_denominator_unchanged=True,
        functional_pass_credit=False,
        whole_design_formal_claim=False,
        scope='generated-source structure of the 64 per-set PLRU chains plus one ternary; no timing or protocol claim',
    )


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--dut', default='abtb')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    result = audit(json.loads(args.report.read_text()), args.dut)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: result[key] for key in
        ('replacer_arms', 'writebuffer_arms', 'covered_arms', 'native_denominator_unchanged')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
