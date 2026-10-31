"""Source-bound MiniConfig MainBTB branch proof, without coverage waivers.

This checks exact generated hierarchy connections and exhaustive Boolean
conditions. It does not prove functional completeness or integrated FTQ safety.
"""
from suites.frontend.bpu import ROOT as _SUITE_ROOT
from datetime import datetime
from datetime import timezone
from hashlib import sha256
import itertools
import json
from pathlib import Path
import re

ROOT = _SUITE_ROOT
SOURCES = ('rtl/mbtb/MainBtbAlignBank.sv', 'rtl/mbtb/MainBtbAlignBank_1.sv',
    'rtl/mbtb/MainBtbInternalBank.sv', 'rtl/mbtb/Queue2_MainBtbCounterSramWriteReq.sv',
    'rtl/mbtb/ram_2x12.sv')


def _line_map(sources):
    return {name: [re.sub(r'\s+', ' ', line.split('//', 1)[0]).strip()
                   for line in text.splitlines()] for name, text in sources.items()}


def audit(sources=None):
    sources = sources or {name: (ROOT / name).read_text() for name in SOURCES}
    lines = _line_map(sources)
    parents = []
    for name in SOURCES[:2]:
        source = lines[name]
        definition = "wire [1:0] s2_multiHitMask = {s2_multiHitMask_multiHitMask_1, 1'h0};"
        assert source.count(definition) == 1, f'{name}: flush mask bit zero must be constant zero'
        connections = [index + 1 for index, line in enumerate(source)
                       if re.fullmatch(r'\.io_flush_req_bits_wayMask\s*\(s2_multiHitMask\)', line)]
        assert len(connections) == 2, f'{name}: both internal banks must use that exact flush mask'
        parents.append(dict(file=name, constant_definition_line=source.index(definition) + 1,
                            definition=definition, internal_bank_connections=connections))
    child = lines[SOURCES[2]]
    assert child[135] == 'writeValid = io_writeEntry_req_valid & io_writeEntry_req_bits_wayMask[0];'
    assert child[136] == 'valid = writeValid | io_flush_req_valid & io_flush_req_bits_wayMask[0] & ~conflict;'
    assert child[148] == 'if (valid) begin'
    assert child[163] == 'end'
    assignments = []
    for number, field in zip(range(151, 164, 2), ('setIdx', 'entry_tag', 'entry_attribute_branchType',
            'entry_attribute_rasAction', 'entry_position', 'entry_targetCarry_value', 'entry_targetLowerBits'), strict=True):
        expected = f'writeValid ? io_writeEntry_req_bits_{field} : '
        assert child[number - 1].startswith(expected), f'changed port-zero payload mux at {number}'
        assert child[number - 2].startswith('entryWriteBuffer_io_write_0_bits_') and child[number - 2].endswith(' <=')
        assignments.append(dict(file=SOURCES[2], line=number, arm='cond_else',
            outer_guard_line=149, expression=child[number - 1],
            contradiction='valid AND NOT writeValid, with flush wayMask[0] permanently zero'))
    truth_table = []
    for training_valid, training_way_zero, flush_valid, conflict in itertools.product((False, True), repeat=4):
        write_valid = training_valid and training_way_zero
        valid = write_valid or (flush_valid and False and not conflict)
        assert not (valid and not write_valid)
        truth_table.append(dict(training_valid=training_valid, training_way_zero=training_way_zero,
            flush_valid=flush_valid, conflict=conflict, write_valid=write_valid,
            capture_enabled=valid, else_arm_reachable=False))
    # Removing the hierarchy premise makes the very same branch reachable.
    without_constant_zero = dict(training_valid=False, training_way_zero=False,
        flush_valid=True, flush_way_zero=True, conflict=False,
        write_valid=False, capture_enabled=True, else_arm_reachable=True)
    ram_parent = lines[SOURCES[3]]
    assert ram_parent.count('.R0_en (1\'h1),') == 1
    assert any('ram_2x12 ram_ext (' in line for line in ram_parent)
    ram = lines[SOURCES[4]]
    assert ram[87] == "assign R0_data = R0_en ? Memory[R0_addr] : 12'bx;"
    assignments.append(dict(file=SOURCES[4], line=88, arm='cond_else',
        parent_file=SOURCES[3], constant_connection_line=ram_parent.index(".R0_en (1'h1),") + 1,
        expression=ram[87], contradiction='R0_en permanently one at the only generated queue RAM instance'))
    return dict(scope='generated two-way standalone MainBTB hierarchy only', parents=parents,
        branches=assignments, truth_table=truth_table, without_hierarchy_premise=without_constant_zero,
        no_denominator_subtraction=True, functional_completeness_claim=False)


def main():
    sources = {name: (ROOT / name).read_text() for name in SOURCES}
    result = audit(sources)
    controls = []
    for label, name, before, after in (
        ('flush-way-zero-not-constant', SOURCES[0], "{s2_multiHitMask_multiHitMask_1, 1'h0}", "{s2_multiHitMask_multiHitMask_1, 1'h1}"),
        ('payload-capture-not-gated', SOURCES[2], 'if (valid) begin', 'if (valid | io_flush_req_valid) begin'),
        ('valid-not-write-or-masked-clear', SOURCES[2], 'valid = writeValid | io_flush_req_valid & io_flush_req_bits_wayMask[0] & ~conflict;', 'valid = io_flush_req_valid | writeValid;'),
        ('ram-read-enable-not-constant', SOURCES[3], ".R0_en   (1'h1)", ".R0_en   (1'h0)"),
    ):
        changed = dict(sources)
        assert before in changed[name]
        changed[name] = changed[name].replace(before, after, 1)
        try:
            audit(changed)
        except AssertionError:
            controls.append(dict(mutation=label, rejected=True))
        else:
            raise AssertionError(f'source proof admitted broken premise: {label}')
    assert len(controls) == 4
    result.update(format='bpu-mbtb-structural-branch-proof', version=1,
        generated_at=datetime.now(timezone.utc).isoformat(),
        source_sha256={name: sha256(text.encode()).hexdigest() for name, text in sources.items()},
        source_mutation_negative_controls=controls, formal_credit=False, goal_complete=False)
    output = ROOT / 'results/coverage-mbtb-branch-unreachable.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print('Eight structurally unreachable branch arms; 16 Boolean cases and four rejected source mutations; raw denominators unchanged')


if __name__ == '__main__':
    main()
