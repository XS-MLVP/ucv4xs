"""Suite roots are stable full-qualified namespaces, not top-level aliases."""
import ast
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ucv.runtime import suite_python_sources

ROOT=Path(__file__).resolve().parents[1]
SUITES=sorted(path.parent for path in (ROOT/'suites').glob('*/*/ucv.json'))


@pytest.mark.parametrize('directory',SUITES,ids=lambda path:path.name)
def test_suite_root_is_the_package_and_resource_anchor(directory):
    name='.'.join(directory.relative_to(ROOT).parts)
    module=importlib.import_module(name)
    assert Path(module.__file__).parent == directory
    assert module.ROOT == directory
    assert not list(directory.glob('*verify'))
    assert not (directory/'common').exists()


def test_multiple_suite_implementations_import_outside_checkout(tmp_path):
    modules=['suites.frontend.bpu.ports.bindings','suites.frontend.ftq.ports',
             'suites.frontend.icache.runtime.dut','suites.frontend.ifu.harness',
             'suites.memblock.lsq.native','suites.memblock.mmu.native',
             'suites.memblock.dcache.native','suites.memblock.lsu.native',
             'suites.memblock.sbuffer.native','suites.vector.vagq.runtime']
    code='''import importlib,json,sys
modules=json.loads(sys.argv[1])
for name in modules: importlib.import_module(name)
assert not any(name in sys.modules for name in ['common','duts','lsqverify','bpuverify'])
print(len(modules))
'''
    env={**os.environ,'PYTHONPATH':str(ROOT),'PYTHONDONTWRITEBYTECODE':'1'}
    result=subprocess.run([sys.executable,'-B','-c',code,json.dumps(modules)],
                          cwd=tmp_path,env=env,text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert result.stdout.strip()==str(len(modules))


def test_suite_source_inventory_skips_evidence_and_generated_links(tmp_path):
    (tmp_path/'driver.py').write_text('')
    (tmp_path/'tests').mkdir();(tmp_path/'tests/test_case.py').write_text('')
    for name in ['results','dut','rtl','__pycache__']:
        (tmp_path/name).mkdir();(tmp_path/name/'generated.py').write_text('')
    outside=tmp_path.parent/(tmp_path.name+'-outside');outside.mkdir()
    (outside/'external.py').write_text('')
    (tmp_path/'external').symlink_to(outside,target_is_directory=True)
    assert [str(p.relative_to(tmp_path)) for p in suite_python_sources(tmp_path)]==[
        'driver.py','tests/test_case.py']


def test_implementation_never_imports_test_support():
    offenders=[]
    for directory in SUITES:
        for path in suite_python_sources(directory):
            if set(path.relative_to(directory).parts) & {'tests','tools'}:
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node,ast.ImportFrom) and (node.module or '').startswith('tests.'):
                    offenders.append(f'{path}:{node.lineno}:{node.module}')
    assert offenders==[]


def test_native_inventories_do_not_collide_in_one_process():
    from suites.memblock.dcache import inventory as dcache
    from suites.memblock.lsu import inventory as lsu
    from suites.memblock.dcache import native as dcache_native
    from suites.memblock.lsu import native as lsu_native
    assert dcache_native.DUTS is dcache.DUTS
    assert lsu_native.DUTS is lsu.DUTS
    assert dcache.DUTS is not lsu.DUTS
    assert 'dcache' in dcache.DUTS and 'load_s2' not in dcache.DUTS
    assert 'load_s2' in lsu.DUTS and 'dcache' not in lsu.DUTS
    assert dcache.dut_dir('probe_queue')==dcache.ROOT/'dut/probe_queue'
    assert lsu.dut_dir('load_s2')==lsu.ROOT/'dut/load_s2'
