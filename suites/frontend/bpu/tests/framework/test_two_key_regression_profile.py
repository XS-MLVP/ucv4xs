"""Semantic programs are production; physical copies remain explicit and complete."""
import ast
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('profile,count',(('production',12),('physical',192)))
def test_real_collection_is_independently_schedulable_without_skipping_or_inner_enumeration(profile,count):
    result=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider','--collect-only',
        '--regression-profile='+profile,'tests/mbtb/testcase/test_entry_keys.py'],
        cwd=ROOT,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    nodes=[line for line in result.stdout.splitlines() if line.startswith('tests/') and '::' in line]
    assert len(nodes)==len(set(nodes))==count
    assert ('replica' in nodes[0])==(profile=='physical')
    tree=ast.parse((ROOT/'tests/mbtb/testcase/test_entry_keys.py').read_text())
    assert not any(isinstance(n,(ast.For,ast.AsyncFor,ast.While)) for n in ast.walk(tree))


def test_optional_physical_holes_do_not_mask_missing_semantic_obligations():
    from copy import deepcopy
    from tests.framework.test_parallel_matrices import full_report,GATE
    report=full_report(representative_only=True)
    result=GATE.validate_parallel_case_coverage(report)
    assert result['mbtb_entry_key_physical']==dict(total_bins=576,coverage=6.25,full_required=False)
    with pytest.raises(ValueError):GATE.validate_parallel_case_coverage(report,profile='physical')
    broken=deepcopy(report)
    with pytest.raises(ValueError):GATE.validate_parallel_case_coverage(full_report(missing_extra_bin='mbtb_two_key_lifetime_checked'))
