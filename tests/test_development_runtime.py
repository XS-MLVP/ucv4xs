"""Local development runtimes must be explicit and verifiable, not forged pins."""
from types import SimpleNamespace

import pytest

from ucv.common import digest, file_hash, write
from ucv.config import Project
from ucv.runtime import validate_development_runtime


def test_runtime_python_is_local_configuration(tmp_path):
    project=Project.__new__(Project)
    project.root=tmp_path
    project.local={}
    assert project.runtime_python()==tmp_path/'.venv/bin/python'
    project.local={'runtime_environment':'.venv-uc-toffee'}
    assert project.runtime_python()==tmp_path/'.venv-uc-toffee/bin/python'
    project.local={'runtime_environment':str(tmp_path/'external-venv')}
    assert project.runtime_python()==tmp_path/'external-venv/bin/python'


@pytest.fixture
def development(tmp_path,monkeypatch):
    import ucv.runtime as runtime
    source=tmp_path/'toffee-source'
    package=tmp_path/'.venv-dev/lib/toffee'
    (source/'src/toffee').mkdir(parents=True)
    package.mkdir(parents=True)
    for root in (source/'src/toffee',package):
        (root/'__init__.py').write_text('"""test package"""\n')
    files={'src/toffee/__init__.py':file_hash(source/'src/toffee/__init__.py')}
    receipt=dict(base_commit='a'*40,distribution='uc-toffee',package_version='2.0.1.dev1',
                 source_files=files,source_sha256=digest(files),wheel_sha256='b'*64,
                 package_files={'__init__.py':file_hash(package/'__init__.py')},
                 runtime_binding={'distribution':'uc-xcomm','package_version':'1.1.1',
                                  'native_abi':3,'coverage_protocol':5})
    write(tmp_path/'.ucv/runtime.json',receipt)
    monkeypatch.setattr(runtime,'version',lambda name: {'uc-toffee':'2.0.1.dev1','uc-xcomm':'1.1.1'}[name])
    monkeypatch.setattr(runtime,'git',lambda path,*args: ('a'*40 if args[0]=='rev-parse' else
        '\0'.join(str(p.relative_to(source)) for p in sorted(source.rglob('*.py')))))
    monkeypatch.setattr(runtime,'validate_binding_identity',lambda binding,pin: None)
    project=SimpleNamespace(root=tmp_path,tools={'xcomm':{'package_version':'0.3.0.dev3'}},
                            runtime_python=lambda:tmp_path/'.venv-dev/bin/python')
    module=SimpleNamespace(__file__=str(package/'__init__.py'))
    arguments=(project,module,module,{'source':str(source),'receipt':'.ucv/runtime.json'})
    return source,package,arguments


def test_development_receipt_does_not_relabel_native_builds(development):
    source,package,arguments=development
    result=validate_development_runtime(*arguments)
    assert result['mode']=='development'
    assert result['source']==str(source)
    assert result['runtime_binding']['package_version']=='1.1.1'
    assert result['native_dut_binding']['package_version']=='0.3.0.dev3'


def test_development_source_changes_are_rejected(development):
    source,package,arguments=development
    (source/'src/toffee/__init__.py').write_text('changed')
    with pytest.raises(RuntimeError,match='source changed'):
        validate_development_runtime(*arguments)


def test_development_untracked_code_is_not_ignored(development):
    source,package,arguments=development
    (source/'src/toffee/extra.py').write_text('new code')
    with pytest.raises(RuntimeError,match='source changed'):
        validate_development_runtime(*arguments)


def test_installed_development_edits_are_rejected(development):
    source,package,arguments=development
    (package/'__init__.py').write_text('changed')
    with pytest.raises(RuntimeError,match='differs from source'):
        validate_development_runtime(*arguments)


def test_installed_stale_extra_files_are_rejected(development):
    source,package,arguments=development
    (package/'stale.py').write_text('old code')
    with pytest.raises(RuntimeError,match='file set differs'):
        validate_development_runtime(*arguments)
