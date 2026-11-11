"""Default discovery must survive the real DCache cwd isolation under xdist."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('workers',[1,2])
@pytest.mark.parametrize('fails',[False,True],ids=['normal','body-failure'])
def test_default_dcache_collection_and_execution_cwd(tmp_path,workers,fails):
    tests=tmp_path/'tests';tests.mkdir()
    source=ROOT/'suites/memblock/dcache/conftest.py'
    (tests/'conftest.py').write_text(source.read_text()+'''

def pytest_sessionfinish(session):
    assert Path.cwd()==Path(session.config.invocation_params.dir)
''')
    body='''from pathlib import Path
def test_native_side_effect(isolated_workdir):
    assert Path.cwd()==isolated_workdir
    Path('memory-direct.fst').write_text('simulated native default dumpfile')
'''
    if fails:
        body+="    assert False, 'intentional body failure'\n"
    (tests/'test_native_side_effect.py').write_text(body)
    ini=tmp_path/'pytest.ini';ini.write_text('[pytest]\n')
    env={**os.environ,'PYTHONPATH':os.pathsep.join([str(ROOT/'src'),str(ROOT)]),
         'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'}
    command=[sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',
             '-p','xdist.plugin','-n',str(workers),'-c',str(ini),
             '--rootdir='+str(tmp_path),'-o','testpaths='+str(tests)]
    result=subprocess.run(command,cwd=tmp_path,env=env,text=True,
                          capture_output=True,timeout=60)
    assert result.returncode==int(fails),result.stdout+result.stderr
    assert ('1 failed' if fails else '1 passed') in result.stdout
    if fails:
        assert 'intentional body failure' in result.stdout
    assert not list(tmp_path.rglob('memory-direct.fst'))
