"""Source-bound, two-state guard proofs; never filter native denominators.

Sixteen generated decrement copies contradict their own priority selector.
Sixteen others require simultaneous call and return commit flags that the parent
cannot produce. This is a bounded guard/input-relation proof, not whole-design
formal reachability or evidence that every other uncovered line is reachable.
"""
from suites.frontend.bpu import ROOT as _SUITE_ROOT
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re


ROOT = _SUITE_ROOT
CHILD = 'rtl/ras/RasStack.sv'
PARENT = 'rtl/ras/Ras.sv'


def witnesses(kind, *, relax=False):
    if kind == 'priority':
        return [dict(pop=pop, repeat=repeat, selected=selected)
                for pop, repeat, selected in product((False, True), repeat=3)
                if pop and repeat and selected and (relax or not selected)]
    if kind == 'parent-action':
        if relax:
            return [dict(push=True, pop=True)]
        return [dict(valid=valid, action=action)
                for valid, action in product((False, True), range(4))
                if valid and action == 2 and action == 1]
    raise ValueError('unsupported RAS guard proof')


def inspect_sources(root=ROOT):
    root = Path(root)
    originals = (root / CHILD).read_text().splitlines()
    child = [line.split('//', 1)[0].strip() for line in originals]
    parent = [line.split('//', 1)[0].strip() for line in (root / PARENT).read_text().splitlines()]
    bindings = {
        'push': ".io_commit_pushValid         (commitValid & commitInfo_attribute_rasAction == 2'h2),",
        'pop': ".io_commit_popValid          (commitValid & commitInfo_attribute_rasAction == 2'h1),",
    }
    binding_lines = {}
    for kind, expected in bindings.items():
        matches = [index for index, line in enumerate(parent) if line == expected]
        if len(matches) != 1:
            raise ValueError(f'RAS parent {kind} relation changed')
        binding_lines[kind] = matches[0] + 1

    def unique(text):
        found = [index for index, line in enumerate(child) if re.sub(r'^wire\s+', '', line) == text]
        if len(found) != 1:
            raise ValueError(f'RAS lexical anchor changed: {text}')
        return found[0]

    def block(start):
        if not child[start].endswith('begin'):
            raise ValueError('RAS guard block must start with begin')
        depth = 0
        for index in range(start, len(child)):
            for token in re.findall(r'\bbegin\b|\bend\b', child[index]):
                depth += 1 if token == 'begin' else -1
                if depth == 0:
                    return index
        raise ValueError('unterminated RAS guard block')

    outer = unique('if (io_commit_pushValid) begin')
    end = block(outer)
    increment = outer + 1
    if child[increment] != 'if (_GEN_49) begin':
        raise ValueError('RAS increment priority changed')
    increment_end = block(increment)
    if child[increment_end + 1] != 'else begin':
        raise ValueError('RAS allocation alternative changed')
    rows = []
    for index in range(outer + 1, end):
        match = re.fullmatch(r'commitStack_(\d+)_ctr <= _commitStack_ctr_T;', child[index])
        if match is None:
            continue
        slot = int(match[1])
        guard = f'_GEN_{19 + 2 * slot}' if slot < 15 else '_GEN_48'
        if child[index - 1] != f'else if ({guard})':
            raise ValueError('RAS decrement immediate guard changed')
        selected = f'_GEN_{18 + 2 * slot}' if slot < 15 else '(&io_commit_metaSsp)'
        definition = unique(f'{guard} = io_commit_popValid & (|_GEN_17) & {selected};')
        if slot < 15:
            unique(f'{selected} = io_commit_metaSsp == 4\'h{slot:X};')
        kind = 'priority' if index < increment_end else 'parent-action'
        if kind == 'priority':
            selector = f'_GEN_{18 + 2 * slot}' if slot < 15 else '&io_commit_metaSsp'
            if child[index - 3] != f'if ({selector})' or child[index - 2] != f'commitStack_{slot}_ctr <= _commitStack_ctr_T_2;':
                raise ValueError('RAS selector priority changed')
        if witnesses(kind) or not witnesses(kind, relax=True):
            raise AssertionError('guard proof or negative control failed')
        rows.append(dict(file=CHILD, line=index + 1, slot=slot, kind=kind,
            verilog=originals[index].strip(), outer_push_line=outer + 1,
            immediate_guard_line=index, guard_definition_line=definition + 1,
            constraint='!selected && pop && nonzero_count && selected' if kind == 'priority'
                       else 'commit_valid && action==2 && action==1',
            satisfying_valuations=0, negative_control=witnesses(kind, relax=True)[0]))
    if len(rows) != 32 or [(row['kind'], row['slot']) for row in rows] != [
            (kind, slot) for kind in ('priority', 'parent-action') for slot in range(16)]:
        raise ValueError('RAS generated decrement-copy layout changed')
    return dict(rows=rows, parent_binding_lines=binding_lines,
                source_sha256={name: sha256((root / name).read_bytes()).hexdigest() for name in (PARENT, CHILD)})


def audit(native, *, root=ROOT):
    proof = inspect_sources(root)
    coverage = native['dut']['ras']
    missing = {(row['file'], row['line']): row for row in coverage['uncovered_rtl_source_lines']}
    proved = {(row['file'], row['line']): row for row in proof['rows']}
    if set(proved) != set(missing):
        raise ValueError('RAS current uncovered set differs from the thirty-two source-bound guard rows')
    for key, row in proved.items():
        if row['verilog'] != missing[key]['verilog'].strip():
            raise ValueError('RAS native report source text changed')
    return dict(format='bpu-ras-generated-guard-audit', version=1,
        proof_scope='source-bound two-state local guards and exact parent input relations; NOT whole-RTL formal proof',
        metric=native['line_coverage'], native_source_lines=coverage['source_lines'],
        native_denominator_unchanged=True, classified_rows=32, functional_points_inferred_missing=0,
        build_provenance=coverage['build_provenance'], **proof)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads(args.native_report.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('native_source_lines', 'classified_rows', 'proof_scope')}))


if __name__ == '__main__':
    main()
