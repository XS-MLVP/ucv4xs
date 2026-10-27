"""Full live checks and independent in-memory reset replay before FC credit."""

from bpuverify.common.coverage.exports import write_functional_coverage
import json
from toffee import CoverageDatabase
from toffee import ScoreboardMismatch
from bpuverify.bpu.case.sc.used import check_used
from bpuverify.bpu.checker.sc.used_audit import samples_from_raw, used_fault_targets
from bpuverify.bpu.coverage.sc.used import used_coverage
from bpuverify.bpu.checker.sc.reset_replay import replay

async def run_used_case(agent, output, *, bank, way, profile):
    trace = await check_used(agent, output, profile, bank=bank, way=way)
    summary, checker = replay(trace)
    for field in ('observed_cycles', 'accepted_feedback', 'full_training_read_responses', 'confirmed_full_shadow_actions', 'full_dirty_overwrite_actions', 'threshold_values', 'reset_derived_threshold_checks'):
        checker.check(trace['summary'][field], summary[field], field='complete_reset_replay_' + field)
    samples = samples_from_raw(trace)
    expected = {'used_correct_' + profile, 'used_wrong'}
    checker.check({(bank, way, kind) for kind in expected}, {(row['bank'], row['way'], row['kind']) for row in samples}, field='actual_physical_used_matrix_case')
    targets = [row for row in used_fault_targets(trace) if row['label'].startswith('used_wrong.') and row['label'].endswith(('.public_used', '.T2_write_gate', '.threshold_update_or_hold'))]
    checker.check(3, len(targets), field='three_targeted_raw_faults')
    failures = []
    for target in targets:
        try:
            replay(trace, fault=target)
        except ScoreboardMismatch as error:
            checker.check(target['tick'], error.replay_tick, field='fault_detected_at_target_tick')
            checker.check(1, error.replay_checker.scoreboard.status.failed, field='fault_raises_one_contextual_mismatch')
            failures.append(dict(label=target['label'], detected_tick=error.replay_tick, field=error.context.request['field']))
        else:
            raise AssertionError(('raw SC-used fault escaped', target))
    group = used_coverage()
    for sample in samples:
        group.sample(sample)
    write_functional_coverage(CoverageDatabase([group]), output / f'functional-coverage-sc-used-bank{bank}-way{way}-{profile}.json')
    compact = dict(bank=bank, way=way, profile=profile, samples=samples, live_summary=trace['summary'], reset_replay_summary=summary, actual_raw_fault_rejections=failures, full_cycle_trace_export=False, full_physical_matrix_qualified=False, nonzero_common_history_closed=False, full_FTQ_legality_proven=False, formal_credit=False)
    (output / 'probe-summary.json').write_text(json.dumps(compact, indent=2) + '\n')
