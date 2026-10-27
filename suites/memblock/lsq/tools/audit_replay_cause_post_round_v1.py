#!/usr/bin/env python3
"""Integrate the cause-lifetime evidence graph without rerunning old rounds."""
import contextlib
import io
import json
from pathlib import Path

from audit_coverage_points_v1 import sha256_file
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases, failure_digest
from audit_failure_preservation_v1 import pytest_status
from audit_final_evidence_matrix_v1 import audit as matrix_audit
from audit_replay_cause_lifetimes_v1 import FULL, BASE, PAIRS, NEW, audit_full, audit_pair
from audit_replay_nc_next_selection_v1 import audit as next_selection_audit
from audit_replay_cause_gain_attribution_v1 import audit as cause_gain_audit
from audit_replay_cause_correction_equivalence_v1 import audit as correction_audit
from audit_refill_width_source_projection_v1 import OUT as WIDTH_CORRECTION, audit as width_source_audit

ROOT = Path(__file__).resolve().parents[1]
UNIFIED = ROOT / 'results/lsq-progress-regression-15'
INPUT = UNIFIED / 'Replay-cause-bit5-integration-input-guard-v1.json'
POST = UNIFIED / 'Replay-cause-bit5-post-index-guard-v1.json'
CHANGING = {f'results/lsq-progress-regression-15/{name}' for name in (
    'gap-closure-summary-v1.json', 'failure-preservation-audit-v1.json',
    'post-regression-required-gates-v1.json', 'final-evidence-matrix-v1.json')}


def load(path):
    return json.loads(path.read_text())


def preserved(name, digest):
    path = ROOT / name
    if sha256_file(path) == digest:
        return path
    archive = path.parent / 'audit-history' / f'{path.stem}-{digest}.json'
    assert sha256_file(archive) == digest
    return archive


def protect():
    if INPUT.exists():
        guard = load(INPUT)
    else:
        old = load(UNIFIED / 'Replay-cause-pre-integration-guard-v1.json')
        assert len(old['old_report_SHA256s']) == 61
        width = width_source_audit()
        for name, digest in old['old_report_SHA256s'].items():
            if name in CHANGING or name in width['prior_report_SHA256s']: preserved(name, digest)
            else: assert sha256_file(ROOT / name) == digest
        first = load(UNIFIED / 'Replay-cause-integration-input-guard-v1.json')
        assert all(sha256_file(ROOT / name) == digest for name, digest in first['protected_raw_artifact_SHA256s'].items())
        raw = dict(first['protected_raw_artifact_SHA256s'])
        first_post = load(UNIFIED / 'Replay-cause-post-index-guard-v1.json')
        assert all(sha256_file(ROOT / name) == digest for name, digest in first_post['protected_raw_artifact_SHA256s'].items())
        raw.update(first_post['protected_raw_artifact_SHA256s'])
        second = load(UNIFIED / 'Replay-cause-corrected-integration-input-guard-v1.json')
        assert all(sha256_file(ROOT / name) == digest for name, digest in second['protected_raw_artifact_SHA256s'].items())
        raw.update(second['protected_raw_artifact_SHA256s'])
        for name, digest in first_post['critical_report_SHA256s'].items():
            preserved(name, digest)
        prior_indexes = {name: sha256_file(ROOT / name) for name in sorted(CHANGING)}
        prior_integration = 'results/lsq-progress-regression-15/Replay-cause-integration-v1.json'
        runs = ['replay-cause-lifetimes-probe-01', 'replay-cause-lifetimes-probe-02',
            'replay-cause-lifetimes-probe-03', 'replay-cause-lifetimes-contributor-regression-01',
            'replay-cause-lifetimes-contributor-regression-02', FULL]
        runs += [f'{prefix}-cause-lifetimes-{kind}-01' for prefix in ('lrq', 'lq', 'lsq') for kind in ('before', 'after')]
        runs += [f'{prefix}-cause-lifetimes-{kind}-02' for prefix in ('lrq', 'lq', 'lsq') for kind in ('before', 'after')]
        runs += [name for _, before, after in PAIRS for name in (before, after)]
        for run in runs:
            directory = ROOT / 'results' / run
            manifest = load(directory / 'execution/manifest.json')
            assert manifest['state'] == 'committed' and manifest['coverage_complete'] and manifest['cleanup_complete']
            paths = [directory / name for name in ('execution/manifest.json', 'pytest.xml', 'command.json',
                'console.log', 'source-aggregate-launch.json', 'source-aggregate-end.json')]
            paths += [Path(artifact['path']) for artifact in manifest['artifacts']]
            paths += list((directory / 'cases').rglob('replay-cause-lifetime-witness.json'))
            for path in paths:
                raw[str(path.relative_to(ROOT))] = sha256_file(path)
        for path in (ROOT / 'results' / FULL / 'whole-runner-receipt.json',
            ROOT / 'results/replay-cause-lifetimes-contributor-regression-01/whole-runner-receipt.json',
            ROOT / 'results/replay-cause-lifetimes-contributor-regression-02/whole-runner-receipt.json',
            UNIFIED / 'Replay-cause-post-audit-01.log', UNIFIED / 'Replay-cause-post-audit-receipt-v1.json'):
            raw[str(path.relative_to(ROOT))] = sha256_file(path)
        guard = dict(format='lsq-Replay-cause-corrected-integration-input-guard-v1',
            old_report_SHA256s=old['old_report_SHA256s'], protected_raw_artifact_SHA256s=dict(sorted(raw.items())),
            original_failed_post_index_critical_SHA256s=first_post['critical_report_SHA256s'],
            pre_corrected_current_index_SHA256s=prior_indexes,
            pre_corrected_integration_SHA256s={prior_integration: sha256_file(ROOT / prior_integration)},
            explicit_old_source_admission_retraction_SHA256s=width['prior_report_SHA256s'],
            only_four_prior_indexes_change=sorted(CHANGING))
        write_report(INPUT, guard)
    assert all(sha256_file(ROOT / name) == digest for name, digest in guard['protected_raw_artifact_SHA256s'].items())
    for field in ('original_failed_post_index_critical_SHA256s', 'pre_corrected_current_index_SHA256s',
        'pre_corrected_integration_SHA256s'):
        for name, digest in guard[field].items():
            preserved(name, digest)
    for name, digest in guard['old_report_SHA256s'].items():
        if name in CHANGING or name in guard['explicit_old_source_admission_retraction_SHA256s']:
            preserved(name, digest)
        else:
            assert sha256_file(ROOT / name) == digest
    return guard


def baseline(guard, filename):
    name = 'results/lsq-progress-regression-15/' + filename
    return load(preserved(name, guard['old_report_SHA256s'][name]))


def rebuild(guard, full):
    path = ROOT / 'results' / FULL / 'Replay-cause-lifetime-contributor-evidence-v1.json'
    assert full['status']['pytest_exitstatus'] == 1 and full['status']['manifest_tests'] == {'PASS': 1569, 'FAIL': 196}
    m = load(ROOT / 'results' / FULL / 'execution/manifest.json')
    assert len([a for a in m['artifacts'] if a['kind'] == 'native']) == len(full['rows']) == 9
    old, new = cases(BASE), cases(FULL)
    assert len(old) == 1762 and len(new) == 1765 and all(new[n] == v for n, v in old.items())
    assert failure_digest(old) == failure_digest(new) == full['current_failure_SHA256']
    gap = baseline(guard, 'gap-closure-summary-v1.json')
    assert len(gap['directed_supplements']) == 47
    for dut, _, after in PAIRS:
        d = ROOT / 'results' / after
        closure_path = d / f'directed-gap-closure-{dut}-v1.json'
        closure = load(closure_path)
        evidence_path = d / 'Replay-cause-lifetime-evidence-v1.json'
        evidence = load(evidence_path)
        assert all(closure['verification'].values()) and all(evidence['verification'].values())
        row = next(row for row in full['rows'] if row['dut'] == dut)
        gap['directed_supplements'].append(dict(path=str(closure_path.relative_to(ROOT)),
            **{key: closure[key] for key in ('dut', 'feature_id', 'case_id', 'before_run', 'after_run',
                'native_build_id', 'metrics', 'functional_before', 'functional_after', 'verification')},
            cause_lifetime_evidence=dict(path=str(evidence_path.relative_to(ROOT)), contract=evidence['contract'],
                target_domains=evidence['target_domains'], source_projection=evidence['source_projection'], limits=evidence['limits']),
            actual_complete_nine_build_rerun=dict(path=str(path.relative_to(ROOT)), run=FULL,
                tests=full['status']['manifest_tests'], old_nodes=1762, current_nodes=1765,
                added_passing_nodes=3, metrics=row['metrics'], original_source_line_coverage=row['original_source_line_coverage'],
                coverage_monotonicity=full['coverage_monotonicity'], verification=full['verification'])))
    assert len(gap['directed_supplements']) == 50
    gap['prior_complete_contributor_runs'].append(gap['latest_complete_contributor_run'])
    gap['latest_complete_contributor_run'] = dict(path=str(path.relative_to(ROOT)), run=FULL, native_builds=9,
        tests=full['status']['manifest_tests'], baseline_run=BASE, old_nodes=1762, current_nodes=1765,
        coverage_monotonicity=full['coverage_monotonicity'])
    gap.setdefault('prior_nine_build_remaining_inventories', []).append(gap['current_nine_build_remaining_inventory'])
    gap['current_nine_build_remaining_inventory'] = dict(path=str(path.relative_to(ROOT)),
        unified_classification_changed=False,
        metrics={row['dut']: row['metrics'] for row in full['rows']},
        original_source_line_coverage={row['dut']: row['original_source_line_coverage'] for row in full['rows']},
        remaining_sets_are_subsets_of_verified_baseline_remaining_sets=True)
    original = ROOT / 'results/replay-cause-lifetimes-contributor-regression-01/Replay-cause-lifetime-contributor-evidence-v1.json'
    previous = load(original)
    assert not previous['PA_lastBeat_source_admission']['proven']
    gap['corrected_Replay_cause_producer_scope'] = full['calibration']
    gap['historical_Replay_cause_interface_run'] = dict(path=str(original.relative_to(ROOT)),
        SHA256=sha256_file(original), run=previous['run'], tests=previous['status']['manifest_tests'],
        PA_lastBeat_source_admission=previous['PA_lastBeat_source_admission'], original_raw_results_retained=True)
    gap['fixed_refill_width_admission_retraction'] = dict(path=str(WIDTH_CORRECTION.relative_to(ROOT)),
        SHA256=sha256_file(WIDTH_CORRECTION), fixed_refill_bytes=32, required_PA_bit=5,
        old_normal_RAW_response_and_cause02_source_admission_withdrawn=True,
        current_cause03_everyS3_PA5_independently_checked=True)
    gap['status'] = '50 independent directed reports; actual9build1765nodes retains196FAIL and all original hits. Unified2330nodes/227FAIL and original classification inventory unchanged; whole-LSQ acceptance open.'
    write_report(UNIFIED / 'gap-closure-summary-v1.json', gap)
    failure = baseline(guard, 'failure-preservation-audit-v1.json')
    for _, _, after in PAIRS:
        status = pytest_status(after)
        assert status['pytest_exitstatus'] == status['errors'] == status['skipped'] == status['failures'] == 0
        failure['directed_supplement_runs'].append(status)
    for name in ('lsqverify/replay_cause_lifetimes.py', *NEW.values(), 'tests/replay_cause_probe/test_probe.py'):
        text = (ROOT / name).read_text().lower()
        assert 'skip' not in text and 'xfail' not in text and name not in failure['source_checks']
        failure['source_checks'][name] = dict(SHA256=sha256_file(ROOT / name), contains_skip=False, contains_xfail=False)
    assert len(failure['source_checks']) == 63
    failure['current_Replay_cause_nine_build_rerun'] = dict(**full['status'], baseline_run=BASE,
        old_nodes=1762, current_nodes=1765, original_failure_SHA256=full['original_failure_SHA256'],
        current_failure_SHA256=full['current_failure_SHA256'], evidence=str(path.relative_to(ROOT)),
        all1762old_outcomes_and196failure_details_equal=True, added_passing_nodes=3, calibration=full['calibration'])
    failure['historical_Replay_cause_source_projection_failure'] = gap['historical_Replay_cause_interface_run']
    failure['first_Replay_cause_post_audit_failed'] = dict(actual_exitstatus=1,
        log=full['calibration']['first_post_audit_failure_log'],
        log_SHA256=full['calibration']['first_post_audit_failure_log_SHA256'],
        reason='Necessary01PA/lastBeat domain annotation changed critical reports during the original audit. The original SHA assertion failure is retained; corrected02uses a distinct guard and terminal audit.')
    write_report(UNIFIED / 'failure-preservation-audit-v1.json', failure)
    gates = baseline(guard, 'post-regression-required-gates-v1.json')
    gates['prior_current_required_gates'] = gates['current_required_gates'] + gates['prior_current_required_gates']
    gates['current_required_gates'] = [dict(**full['coverage_monotonicity'], evidence=str(path.relative_to(ROOT)))]
    for item in full['calibration']['historical_interface_runs']:
        gates['domain_limited_supplements'].append(dict(duts=[item['dut']], historical=True,
            domain=item['domain'], evidence=item['evidence'], corrected_current_evidence=str(path.relative_to(ROOT)),
            source_domain_evidence=full['calibration']['source_correction'], normal_full_core_producer_proven=False,
            global_unreachability_proven=False,
            remaining_boundary='Earlier lastBeat input projection was not derived from fixed256bitbus/32Bbeat. Retain actual interface checks; only formal03checks everyS3against PA[5]. Native upstream LoadUnit remains outside the LSQ DUT.'))
    width = width_source_audit()
    gates['domain_limited_supplements'].append(dict(duts=['load_queue_replay', 'load_queue', 'lsq_wrapper'],
        domain=width['domain'], historical=True, evidence=str(WIDTH_CORRECTION.relative_to(ROOT)),
        corrected_current_evidence=str(path.relative_to(ROOT)), normal_full_core_producer_proven=False,
        global_unreachability_proven=False,
        remaining_boundary='Normal metadata,RAW owners,response payload and cause02old helper usedPA6(blocksize64)instead of fixedPA5(refillbeat32). All old raw/FAIL kept; their upstream lastBeat source admission is withdrawn. Only current cause03has corrected evidence.'))
    selection_path = ROOT / 'results' / FULL / 'next-NC-type-lifetimes-selection-v1.json'
    selection = load(selection_path)
    assert selection['native_dynamic_coverage_gain'] == 0 and not selection['next_tests_created']
    gates['supplemental_source_triage'].append(dict(path=str(selection_path.relative_to(ROOT)),
        run=FULL, native_dynamic_coverage_gain=0, full_upstream_legality_proven=False, failure_waived=False,
        selection_only=True, next_contract_created=False, next_tests_created=False))
    write_report(UNIFIED / 'post-regression-required-gates-v1.json', gates)
    matrix = matrix_audit('lsq-progress-regression-15')
    assert len(matrix['rows']) == 38 and matrix['overall_status'] == 'ACTIVE_NOT_ACCEPTED'
    assert matrix['unified_tests'] == {'PASS': 2103, 'FAIL': 227}
    return dict(native_builds=38, independent_directed_reports=50, source_checks=63,
        latest_native_builds=9, latest_tests=full['status']['manifest_tests'], unified_tests=matrix['unified_tests'],
        current_required_gate=gates['current_required_gates'][0],
        required_new_functional_failures=gates['required_new_functional_failures'], overall_status='ACTIVE_NOT_ACCEPTED')


def integrate():
    guard = protect()
    full = audit_full()
    next_selection_audit()
    cause_gain_audit()
    correction_audit()
    index = rebuild(guard, full)
    protect()
    r = dict(format='lsq-Replay-cause-integration-v1', index=index, exitstatus=0, native_DUT_reruns=0,
        old_complete_evidence_graph_reexecuted=False,
        unchanged_old_reports_SHA256_count=sum(name not in CHANGING and name not in guard['explicit_old_source_admission_retraction_SHA256s'] for name in guard['old_report_SHA256s']),
        source_admission_changes_explicitly_SHA_archived=True,
        prior_index_versions={name: str(preserved(name, digest).relative_to(ROOT)) for name, digest in guard['old_report_SHA256s'].items() if name in CHANGING},
        protected_raw_files=len(guard['protected_raw_artifact_SHA256s']), all_raw_hashes_equal=True)
    write_report(UNIFIED / 'Replay-cause-integration-v1.json', r)
    return r


def capture():
    guard = protect()
    paths = list(guard['old_report_SHA256s'])
    for dut, _, after in PAIRS:
        paths += [f'results/{after}/Replay-cause-lifetime-evidence-v1.json', f'results/{after}/directed-gap-closure-{dut}-v1.json']
    paths += [f'results/{FULL}/Replay-cause-lifetime-contributor-evidence-v1.json',
        f'results/{FULL}/PA-lastBeat-correction-equivalence-v1.json',
        f'results/{FULL}/cause-gain-attribution-v1.json',
        f'results/{FULL}/next-NC-type-lifetimes-selection-v1.json',
        'results/replay-cause-lifetimes-probe-01/probe-audit-v1.json',
        'results/replay-cause-lifetimes-probe-02/probe-audit-v1.json',
        'results/replay-cause-lifetimes-probe-03/probe-audit-v1.json',
        'results/replay-cause-lifetimes-contributor-regression-01/PA-lastBeat-source-correction-v1.json',
        'results/replay-cause-lifetimes-contributor-regression-01/Replay-cause-lifetime-contributor-evidence-v1.json',
        'results/replay-cause-lifetimes-contributor-regression-02/refill-width-source-correction-v2.json',
        'results/replay-cause-lifetimes-contributor-regression-02/PA-bit5-producer-correction-v3.json',
        'results/replay-cause-lifetimes-contributor-regression-02/Replay-cause-lifetime-contributor-evidence-v1.json',
        'results/lsq-progress-regression-15/Replay-cause-integration-v1.json']
    paths += [f'results/{prefix}-cause-lifetimes-after-01/Replay-cause-lifetime-evidence-v1.json' for prefix in ('lrq', 'lq', 'lsq')]
    paths += [f'results/{prefix}-cause-lifetimes-after-02/Replay-cause-lifetime-evidence-v1.json' for prefix in ('lrq', 'lq', 'lsq')]
    paths.append('results/replay-cause-lifetimes-probe-02/formal02-PA-recheck-v1.json')
    assert len(paths) == len(set(paths))
    raw = dict(guard['protected_raw_artifact_SHA256s'])
    for name in ('post-regression-Replay-cause-01.log', 'Replay-cause-integration-receipt-v1.json',
        'Replay-cause-old-entrypoint-scope-guard.log', 'post-regression-Replay-cause-index-02.log',
        'Replay-cause-entrypoint-receipt-v1.json', 'post-regression-Replay-cause-corrected-01.log',
        'Replay-cause-corrected-integration-receipt-v1.json', 'Replay-cause-corrected-old-entrypoint-scope-guard.log',
        'post-regression-Replay-cause-corrected-index-02.log', 'Replay-cause-corrected-entrypoint-receipt-v1.json',
        'post-regression-Replay-cause-bit5-01.log', 'Replay-cause-bit5-integration-receipt-v1.json',
        'Replay-cause-bit5-old-entrypoint-scope-guard.log', 'post-regression-Replay-cause-bit5-index-02.log',
        'Replay-cause-bit5-entrypoint-receipt-v1.json'):
        if 'corrected-old-entrypoint' in name or 'corrected-index-02' in name or 'corrected-entrypoint' in name:
            continue  # No02endpoint was claimed after the second source retraction.
        path = UNIFIED / name; raw[str(path.relative_to(ROOT))] = sha256_file(path)
    r = dict(format='lsq-Replay-cause-post-index-guard-v1', index=load(UNIFIED / 'Replay-cause-integration-v1.json')['index'],
        critical_report_SHA256s={name: sha256_file(ROOT / name) for name in paths}, protected_raw_artifact_SHA256s=dict(sorted(raw.items())),
        archives={str(p.relative_to(ROOT)): sha256_file(p) for p in (ROOT / 'results').glob('*/audit-history/*.json')})
    if POST.exists(): assert load(POST) == r
    else: write_report(POST, r)
    return r


def audit():
    guard = load(POST)
    with contextlib.redirect_stdout(io.StringIO()):
        for pair in PAIRS: audit_pair(*pair)
        current = integrate()
    assert current['index'] == guard['index']
    assert all(sha256_file(ROOT / n) == h for n, h in guard['critical_report_SHA256s'].items())
    assert all(sha256_file(ROOT / n) == h for n, h in guard['protected_raw_artifact_SHA256s'].items())
    assert {str(p.relative_to(ROOT)): sha256_file(p) for p in (ROOT / 'results').glob('*/audit-history/*.json')} == guard['archives']
    r = dict(format='lsq-Replay-cause-round-post-audit-v1', index=guard['index'],
        critical_report_SHA256s=guard['critical_report_SHA256s'], critical_reports_idempotent=len(guard['critical_report_SHA256s']),
        protected_raw_artifact_SHA256s=guard['protected_raw_artifact_SHA256s'], protected_raw_files=len(guard['protected_raw_artifact_SHA256s']),
        all_raw_hashes_equal=True, no_duplicate_archive_on_identical_evidence=True, native_DUT_reruns=0,
        full_goal_completion_claimed=False, overall_status='ACTIVE_NOT_ACCEPTED')
    write_report(UNIFIED / 'Replay-cause-round-post-audit-v1.json', r)
    return r


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(); p.add_argument('--integrate', action='store_true'); p.add_argument('--capture', action='store_true'); a = p.parse_args()
    assert not (a.integrate and a.capture)
    r = integrate() if a.integrate else capture() if a.capture else audit()
    print(json.dumps({k: v for k, v in r.items() if not k.endswith('SHA256s')}, indent=2))
