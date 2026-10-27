"""Scope separation cannot hide losses, partial baselines or denominator drift."""
import json
from pathlib import Path

import pytest

from tools import refresh_coverage as refresh
from tools import regression_profiles as profiles


@pytest.fixture
def native(tmp_path):
    reports = []
    for scope, hits in [('published', (1, 1, 0)), ('prior', (1, 0, 0)), ('fresh', (1, 0, 1))]:
        path = tmp_path / (scope + '.info')
        path.write_text('SF:/rtl/source.sv\n' + ''.join(f'DA:{i},{v}\n' for i, v in enumerate(hits, 1)) + 'end_of_record\n')
        reports.append(dict(dut=dict(bpu=dict(lcov_file=str(path)))))
    return reports


def test_initial_representative_measurement_reports_all_cross_scope_losses(native):
    published, prior, fresh = native
    losses, comparison = profiles.compare_native(fresh, published, None, lcov=refresh.lcov)
    assert losses == {}
    assert comparison['initial_profile_measurement']
    assert not comparison['same_profile_baseline_available']
    assert comparison['dut']['bpu'] == dict(total=3, current_hit=2, published_hit=2,
        published_hit_now_unhit=1, published_unhit_now_hit=1)


def test_same_scope_losses_are_never_waived(native):
    published, prior, fresh = native
    losses, comparison = profiles.compare_native(prior, published, fresh, lcov=refresh.lcov)
    assert losses == dict(bpu=[('/rtl/source.sv', 3)])
    assert comparison['same_profile_baseline_available']


def test_cross_scope_change_does_not_disable_source_line_universe_check(native):
    published, prior, fresh = native
    path = Path(fresh['dut']['bpu']['lcov_file'])
    path.write_text('SF:/rtl/source.sv\nDA:1,1\nend_of_record\n')
    with pytest.raises(ValueError, match='denominator changed'):
        profiles.compare_native(fresh, published, None, lcov=refresh.lcov)


@pytest.mark.parametrize('side', ('fresh', 'prior'))
def test_missing_dut_is_rejected(native, side):
    published, prior, fresh = native
    (fresh if side == 'fresh' else prior)['dut'] = {}
    with pytest.raises(ValueError, match='DUT universe changed'):
        profiles.compare_native(fresh, published, prior, lcov=refresh.lcov)


@pytest.fixture
def profile_run(tmp_path):
    run = tmp_path / 'results/qualified-run'
    run.mkdir(parents=True)
    result = dict(regression_profile='production', process_exitstatus=0, full_regression_complete=True)
    native = dict(dut={}, regression_profile='production', selected_measurement=False)
    for name, value in [('summary.json', result), ('exit.json', result), ('rtl-line-coverage.json', native)]:
        (run / name).write_text(json.dumps(value))
    return tmp_path, run


def test_profiles_have_independent_qualified_baselines(profile_run):
    root, run = profile_run
    profiles.publish_index(root, 'production', run, digest=refresh.digest)
    assert profiles.load_baseline(root, 'production', read=refresh.read, digest=refresh.digest)['dut'] == {}
    assert profiles.load_baseline(root, 'physical', read=refresh.read, digest=refresh.digest) is None


@pytest.mark.parametrize('fault', ('partial', 'wrong_profile', 'failed', 'modified', 'native_scope', 'selected_native'))
def test_unqualified_or_changed_baseline_is_rejected(profile_run, fault):
    root, run = profile_run
    result = json.loads((run/'summary.json').read_text())
    if fault == 'partial': result['full_regression_complete'] = False
    if fault == 'wrong_profile': result['regression_profile'] = 'physical'
    if fault == 'failed': result['process_exitstatus'] = 1
    (run/'summary.json').write_text(json.dumps(result))
    if fault in ('native_scope', 'selected_native'):
        native = json.loads((run/'rtl-line-coverage.json').read_text())
        native['regression_profile' if fault == 'native_scope' else 'selected_measurement'] = 'physical' if fault == 'native_scope' else True
        (run/'rtl-line-coverage.json').write_text(json.dumps(native))
    profiles.publish_index(root, 'production', run, digest=refresh.digest)
    if fault == 'modified': (run/'rtl-line-coverage.json').write_text('{}')
    with pytest.raises(ValueError, match='baseline'):
        profiles.load_baseline(root, 'production', read=refresh.read, digest=refresh.digest)


def test_legacy_exhaustive_view_remains_available_after_production_publication(profile_run):
    root, archive = profile_run
    (root/'results/regression-profiles').mkdir()
    summary = dict(full_regression_complete=True, process_exitstatus=0)
    profiles.retain_legacy_baseline(root, archive, summary, digest=refresh.digest)
    assert profiles.load_baseline(root, 'physical', read=refresh.read, digest=refresh.digest)['dut'] == {}
    assert profiles.load_baseline(root, 'production', read=refresh.read, digest=refresh.digest) is None
    (archive/'rtl-line-coverage.json').write_text('{}')
    with pytest.raises(ValueError, match='legacy physical native baseline changed'):
        profiles.load_baseline(root, 'physical', read=refresh.read, digest=refresh.digest)
