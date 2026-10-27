#!/usr/bin/env python3
"""Locate real full-regression gains; do not credit directed-only hits."""
from collections import Counter
import json
from pathlib import Path
import re

from audit_coverage_points_v1 import records, sha256_file
from audit_evidence_io import write_report
from audit_gap_closure_v1 import native, point_key, digest_keys
from audit_replay_cause_lifetimes_v1 import BASE, FULL, NEW, source_projection

ROOT = Path(__file__).resolve().parents[1]


def audit():
    full = json.loads((ROOT / 'results' / FULL / 'Replay-cause-lifetime-contributor-evidence-v1.json').read_text())
    assert all(full['verification'].values())
    rows = []
    for dut in NEW:
        a, da = native(BASE, dut)
        b, db = native(FULL, dut)
        assert a['artifact']['build'] == b['artifact']['build']
        assert sha256_file(da) == a['artifact']['sha256'] and sha256_file(db) == b['artifact']['sha256']
        old, current = records(da), records(db)
        before = {point_key(p) for p in old if p['hit'] and not p['f'].endswith('_top.sv')}
        gained = [p for p in current if p['hit'] and not p['f'].endswith('_top.sv') and point_key(p) not in before]
        source = ROOT / 'dut/load_queue_replay/LoadQueueReplayDut.v' if dut == 'load_queue_replay' else ROOT / 'rtl' / dut / 'LoadQueueReplay.sv'
        text = source.read_text()
        lines = text.splitlines()
        toggle = [p for p in gained if p['t'] == 'toggle']
        branch = [p for p in gained if p['t'] == 'branch']
        assert not any(p['t'] == 'line' for p in gained)
        counts = Counter()
        for p in toggle:
            match = re.fullmatch(r'cause_(\d+)\[(\d+)\]:(0->1|1->0)', p['o'])
            assert p['f'] == str(source) and match and int(match[2]) in (3, 5, 6, 8)
            assert 0 <= int(match[1]) < 120
            counts[(int(match[2]), match[3])] += 1
        baseline_missing = {point_key(p) for p in old if p['t'] == 'toggle' and not p['hit'] and p['f'] == str(source)
            and (match := re.fullmatch(r'cause_\d+\[(\d+)\]:(0->1|1->0)', p['o'])) and int(match[1]) in (3, 5, 6, 8)}
        assert {point_key(p) for p in toggle} == baseline_missing
        predicates = Counter()
        branch_rows = []
        for p in branch:
            statement = lines[int(p['l']) - 1].strip()
            assert dut == 'load_queue' and p['f'] == str(source) and p['o'] == 'cond_then'
            pred = statement.split(' ? ')[0]
            assert pred in ('_GEN_2553', '_GEN_2799')
            predicates[pred] += 1
            branch_rows.append(dict(line=int(p['l']), arm=p['o'], predicate=pred, hierarchy=p['h']))
        if dut == 'load_queue':
            assert predicates == {'_GEN_2553': 120, '_GEN_2799': 120}
            for predicate, intermediate, lane in (
                ('_GEN_2553', '_replayMultiMatchOver4Count_T_7', 1),
                ('_GEN_2799', '_replayMultiMatchOver4Count_T_14', 2),
            ):
                assert re.search(r'wire\s+' + predicate + r'\s*=\s*' + intermediate +
                    r'\s*& io_enq_' + str(lane) + r'_bits_rep_info_need_rep;', text)
                assert re.search(r'wire\s+' + intermediate + r'\s*=\s*io_enq_' + str(lane) +
                    r'_valid & io_enq_' + str(lane) + r'_bits_isLoadReplay;', text)
        else:
            assert not branch
        expected = next(row for row in full['rows'] if row['dut'] == dut)
        assert len(toggle) == expected['metrics']['toggle']['newly_hit']
        assert len(branch) == expected['metrics']['branch']['newly_hit']
        rows.append(dict(dut=dut, source=str(source.relative_to(ROOT)), source_SHA256=sha256_file(source),
            newly_hit_toggle=len(toggle), all_toggle_gains_exactly_previously_missing_cause_bits=True,
            toggle_by_cause_bit_and_direction=[dict(bit=bit, direction=direction, points=count)
                for (bit, direction), count in sorted(counts.items())],
            toggle_gained_point_set_SHA256=digest_keys({point_key(p) for p in toggle}),
            source_declaration_lines=sorted({int(p['l']) for p in toggle}),
            newly_hit_branch=len(branch), branch_predicate_counts=dict(predicates), branch_points=branch_rows,
            branch_gained_point_set_SHA256=digest_keys({point_key(p) for p in branch})))
    result = dict(format='lsq-Replay-cause-full-gain-attribution-v1', run=FULL, baseline_run=BASE, rows=rows,
        semantic_explanation='Cause-register known-write lifetimes supply every previously missing direction of bits3/5/6/8. The240LQ branch gains are ternary then arms for valid && isLoadReplay && need_rep on input1/2; each predicate is distributed to120scheduled-entry decisions. They are evaluation coverage, not240independent completed behaviors or evidence that every slot fed back on every lane.',
        source_projection=source_projection(), native_DUT_reruns=0,
        verification=dict(all3full_toggle_gain_sets_exactly_known_cause_targets=True,
            LQ240branch_points_exactly_valid_reReplay_lane1_and2_predicates=True,
            all_gained_points_have_exact_source_lines_hierarchy_and_identity_hashes=True,
            directed_only_branch_and_toggle_not_credited=True),
        limits='Attribution of this actual complete9build run only. Other cause bits,NC,Store dependencies,strict/disabled,all prior failures and whole38DUT acceptance remain open; no denominator or original classification is edited.')
    write_report(ROOT / 'results' / FULL / 'cause-gain-attribution-v1.json', result)
    return result


if __name__ == '__main__':
    r = audit()
    print(json.dumps(dict(run=r['run'], rows=[{key: row[key] for key in ('dut', 'newly_hit_toggle', 'newly_hit_branch', 'branch_predicate_counts')} for row in r['rows']], verification=r['verification']), indent=2))
