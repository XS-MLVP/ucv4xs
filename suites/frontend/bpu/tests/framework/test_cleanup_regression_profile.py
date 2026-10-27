"""Actual collection and merge gates for independent clear/correction lifetimes."""
from pathlib import Path
import ast
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('profile,count',(('production',12),('physical',48)))
def test_real_collection_has_no_serial_inner_matrix(profile,count):
    result=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider','--collect-only',
        '--regression-profile='+profile,'tests/mbtb/testcase/test_cleanup_overlap.py'],
        cwd=ROOT,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    nodes=[line for line in result.stdout.splitlines() if line.startswith('tests/') and '::' in line]
    assert len(nodes)==len(set(nodes))==count
    assert ('replica' in nodes[0])==(profile=='physical')
    tree=ast.parse((ROOT/'tests/mbtb/testcase/test_cleanup_overlap.py').read_text())
    assert not any(isinstance(n,(ast.For,ast.AsyncFor,ast.While)) for n in ast.walk(tree))


def test_representative_physical_scope_cannot_excuse_missing_semantic_obligations():
    from copy import deepcopy
    from tests.framework.test_parallel_matrices import full_report,GATE
    report=full_report(representative_only=True)
    result=GATE.validate_parallel_case_coverage(report)
    assert result['mbtb_cleanup_physical']==dict(total_bins=144,coverage=25,full_required=False)
    with pytest.raises(ValueError):GATE.validate_parallel_case_coverage(report,profile='physical')
    with pytest.raises(ValueError):GATE.validate_parallel_case_coverage(full_report(missing_extra_bin='mbtb_cleanup_lifetime_checked'))
    missing=deepcopy(report)
    missing['groups']=[g for g in missing['groups'] if g['instance']!='kunminghu_v3.mbtb.cleanup_overlap']
    with pytest.raises(ValueError):GATE.validate_parallel_case_coverage(missing)
