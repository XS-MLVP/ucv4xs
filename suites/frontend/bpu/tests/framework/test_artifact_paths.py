"""Output isolation uses complete test identity, never simulation pointers."""
import asyncio
from pathlib import Path

import pytest

from bpuverify.common.env import artifacts


@pytest.fixture(autouse=True)
def isolated_policy_unit_context():
    # These unit cases explicitly exercise the unbound legacy policy as well
    # as nested bindings; a production pytest owner may already have a scope.
    token = artifacts._case_output.set(None)
    try:
        yield
    finally:
        artifacts._case_output.reset(token)


def test_legacy_output_paths_unchanged_and_no_directory_created(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, 'ROOT', tmp_path)
    assert artifacts.output_directory(tmp_path, 'bpu') == tmp_path / 'results/bpu'
    assert artifacts.output_path('results/bpu/out.json') == Path('results/bpu/out.json')
    assert not artifacts.isolated_outputs()
    assert not (tmp_path / 'results').exists()


def test_full_nodeid_worker_and_parameter_isolate_same_named_output(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, 'ROOT', tmp_path)
    run = tmp_path / 'results/run'
    outputs = []
    for worker in ('main', 'gw0', 'gw1'):
        for nodeid in ('tests/a/test_x.py::test_same[p0]', 'tests/b/test_x.py::test_same[p0]',
                       'tests/a/test_x.py::test_same[p1]'):
            case = artifacts.case_directory(run, worker, nodeid)
            with artifacts.case_outputs(case):
                target = artifacts.output_directory(tmp_path, 'bpu') / 'functional-coverage.json'
                outputs.append(target)
                assert target.is_relative_to(run / 'workers' / worker)
                assert artifacts.output_path(target) == target
    assert len(set(outputs)) == 9
    assert not run.exists()
    assert not artifacts.isolated_outputs()


def test_explicit_external_paths_do_not_get_rewritten(tmp_path, monkeypatch):
    project = tmp_path / 'project'
    monkeypatch.setattr(artifacts, 'ROOT', project)
    external = tmp_path / 'independent/output.json'
    with artifacts.case_outputs(project / 'results/isolated'):
        assert artifacts.output_path(external) == external


def test_nested_scope_and_exception_restore_previous_context(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    with artifacts.case_outputs(first):
        assert artifacts.isolated_outputs()
        with pytest.raises(RuntimeError):
            with artifacts.case_outputs(second):
                assert artifacts.output_path(artifacts.ROOT / 'results/bpu/a') == second / 'bpu/a'
                raise RuntimeError('body failed')
        assert artifacts.output_path(artifacts.ROOT / 'results/bpu/a') == first / 'bpu/a'
    assert not artifacts.isolated_outputs()


async def test_async_children_inherit_case_scope(tmp_path):
    async def child():
        await asyncio.sleep(0)
        return artifacts.output_path(artifacts.ROOT / 'results/bpu/a')
    with artifacts.case_outputs(tmp_path):
        task = asyncio.create_task(child())
        assert await task == tmp_path / 'bpu/a'


@pytest.mark.parametrize('worker', ('../other', '', 'gw-1', 'gwx', None))
def test_invalid_worker_rejected(tmp_path, worker):
    with pytest.raises(ValueError):
        artifacts.case_directory(tmp_path, worker, 'tests/a.py::test_a')


@pytest.mark.parametrize('nodeid', ('', None, 1))
def test_missing_full_nodeid_rejected(tmp_path, nodeid):
    with pytest.raises(ValueError):
        artifacts.case_directory(tmp_path, 'gw0', nodeid)


def test_nodeid_text_cannot_escape_hashed_case_directory(tmp_path):
    path = artifacts.case_directory(tmp_path, 'gw0', '../../other::test_a[../../x]')
    assert path.parent.parent == tmp_path / 'workers/gw0'
    assert len(path.parent.name) == 64


@pytest.mark.parametrize('name', ('../bpu', 'BPU', '', None))
def test_invalid_dut_name_rejected(tmp_path, name):
    with pytest.raises(ValueError):
        artifacts.output_directory(tmp_path, name)


def test_relative_case_directory_rejected():
    with pytest.raises(ValueError):
        with artifacts.case_outputs(Path('relative')):
            pass


def test_write_output_creates_only_the_routed_parent_and_routes_isolated_case(tmp_path, monkeypatch):
    project = tmp_path / 'project'
    monkeypatch.setattr(artifacts, 'ROOT', project)
    run = project / 'results/run'
    original = project / 'results/bpu/deep/known-fail.json'
    with artifacts.case_outputs(run / 'workers/gw0' / ('a' * 64) / 'results'):
        target = artifacts.write_output(original, '{"status": "XFAIL"}\n')
        assert target == run / 'workers/gw0' / ('a' * 64) / 'results/bpu/deep/known-fail.json'
        assert target.read_text() == '{"status": "XFAIL"}\n'
    # Legacy writes are unaltered and still require an existing parent.
    assert not (project / 'results/bpu/deep/known-fail.json').exists()
