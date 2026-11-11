"""Deletion selection must not consume analysis or the last complete run."""
import json
from pathlib import Path
import pytest

import tools.prune_result_artifacts as retention


@pytest.mark.parametrize('name',[
    'old/workers/gw0/native/bpu/native-merged.dat',
    'old/rtl-lines/bpu.info','old/functional-coverage-foo.json',
    'old/functional.json.gz','old/rtl-line-coverage.json',
    'old/coverage.html','old/dump.fst',
    'old/workers/gw0/case/results/bpu/phr-recovery-flowing.json',
    'bpu/integrated-aging-1/integrated-natural-aging-bank1.json',
])
def test_measurement_payload_is_selected(name):
    assert retention.category(Path(name)) is not None


@pytest.mark.parametrize('name',[
    'coverage-gap-diagnosis.json','old/summary.json','old/pytest.xml',
    'old/defect-analysis.json','old/audit.json','old/reproduce.py',
    'old/results/bpu/alignment-summary.json','old/receipt.json',
    'old/native-retention.json','old/unknown-data.json',
])
def test_analysis_and_unknown_files_are_not_selected(name):
    assert retention.category(Path(name)) is None


def test_apply_preserves_latest_analysis_live_baseline_and_symlink_targets(tmp_path,monkeypatch):
    results=tmp_path/'results'
    keep=results/'latest'
    for name in ('latest/execution/native/coverage.dat','old/native/a.dat',
                 'old/results/bpu/raw-trace.json','old/analysis.json',
                 'old/summary.json','baseline/rtl-lines/bpu.info'):
        path=results/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('retained or disposable')
    (results/'rtl-line-coverage.json').write_text(json.dumps({'dut':{'bpu':{
        'lcov_file':str(results/'baseline/rtl-lines/bpu.info')}}}))
    outside=tmp_path/'outside.dat'
    outside.write_text('not ours')
    (results/'linked.dat').symlink_to(outside)
    candidates,kept,plan=retention.snapshot(results,keep)
    assert plan['selected_paths']==2
    monkeypatch.setattr(retention,'check_active',lambda candidates:None)
    result=retention.apply(results,candidates,kept)
    assert result['retained_hashes_verified']
    assert (keep/'execution/native/coverage.dat').exists()
    assert (results/'old/analysis.json').exists()
    assert (results/'old/summary.json').exists()
    assert (results/'baseline/rtl-lines/bpu.info').exists()
    assert outside.read_text()=='not ours'
    assert not (results/'old/native/a.dat').exists()


def test_changed_candidate_aborts_before_any_deletion(tmp_path,monkeypatch):
    results=tmp_path/'results'
    keep=results/'latest'
    keep.mkdir(parents=True)
    first,second=results/'a.dat',results/'b.dat'
    first.write_text('a')
    second.write_text('b')
    candidates,kept,_=retention.snapshot(results,keep)
    second.write_text('changed')
    monkeypatch.setattr(retention,'check_active',lambda candidates:None)
    with pytest.raises(RuntimeError,match='candidate changed'):
        retention.apply(results,candidates,kept)
    assert first.exists() and second.exists()
