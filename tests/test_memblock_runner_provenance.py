"""Legacy direct-run receipts must describe the same default as native argv.

Processes and native packages are stubbed; this tests orchestration/provenance,
not hardware functionality or the real Toffee runner.
"""
import importlib
import json
from types import SimpleNamespace

import pytest

import ucv.runtime
from tests.test_memblock_runtime_seed import LEGACY, fake_package


RECEIPTS = {
    'dcache': ('seed.json', 'verilator_seed'),
    'lsu': ('run-provenance.json', 'verilator_seed'),
    'mmu': ('verification-sources.json', 'seed'),
}


def runner(monkeypatch, tmp_path, suite):
    monkeypatch.setattr(ucv.runtime, 'toolchain', lambda: dict(
        toffee=dict(runner_command=['stub-toffee']),
        verilator=dict(coverage_processor='stub-coverage')))
    module = importlib.import_module(f'suites.memblock.{suite}.tools.run')
    loader = 'dut' if suite == 'dcache' else 'native'
    native = importlib.import_module(f'suites.memblock.{suite}.testbenches.shared.env.{loader}')
    fake_package(monkeypatch, native)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    for name in ('pytest.ini', 'manifest/toolchain.json', 'manifest/lsu-rtl.sha256'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}\n')
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'tests/test_stub.py').write_text('# no native execution\n')
    monkeypatch.setattr('sys.argv', ['run.py', '--name', 'fresh', 'tests/test_stub.py'])
    return module, native


@pytest.mark.parametrize('suite', tuple(RECEIPTS))
@pytest.mark.parametrize('mode', ('default', 'legacy', 'cli-over-legacy', 'changed-after-launch'))
def test_direct_runner_records_the_seed_actually_sent_to_its_child(monkeypatch, tmp_path, suite, mode):
    module, native = runner(monkeypatch, tmp_path, suite)
    monkeypatch.delenv('UCV_SEED', raising=False)
    monkeypatch.delenv(LEGACY[native], raising=False)
    expected = 1
    if mode != 'default':
        monkeypatch.setenv(LEGACY[native], '19')
        expected = 19
    if mode in ('cli-over-legacy', 'changed-after-launch'):
        monkeypatch.setenv('UCV_SEED', '7')
        expected = 7
    children = []

    def launch(command, *, cwd, env, **kwargs):
        children.append(dict(argv=tuple(native._argv(None)), env=dict(env), cwd=cwd))
        if mode == 'changed-after-launch':
            monkeypatch.setenv('UCV_SEED', '29')
            monkeypatch.setenv(LEGACY[native], '31')
        return SimpleNamespace(returncode=0, stdout=iter(('stub child\n',)), wait=lambda: 0)

    monkeypatch.setattr(module.subprocess, 'run', launch)
    monkeypatch.setattr(module.subprocess, 'Popen', launch)
    with pytest.raises(SystemExit) as done:
        module.main()
    assert done.value.code == 0
    assert len(children) == 1
    child, = children
    assert child['argv'][-1] == f'+verilator+seed+{expected}'
    path, field = RECEIPTS[suite]
    receipt = json.loads((tmp_path / 'results/fresh' / path).read_text())
    assert int(receipt[field]) == expected
    # Default selection is frozen before process launch, including the legacy
    # fallback; the child need not repeat an unrecorded environment decision.
    assert child['env']['UCV_SEED'] == str(expected)


@pytest.mark.parametrize('suite', tuple(RECEIPTS))
def test_invalid_seed_fails_before_launch_or_creating_a_receipt(monkeypatch, tmp_path, suite):
    module, _ = runner(monkeypatch, tmp_path, suite)
    monkeypatch.setenv('UCV_SEED', '-1')
    launched = []
    def launch(*args, **kwargs):
        launched.append(kwargs)
        return SimpleNamespace(returncode=0, stdout=iter(()), wait=lambda: 0)
    monkeypatch.setattr(module.subprocess, 'run', launch)
    monkeypatch.setattr(module.subprocess, 'Popen', launch)
    with pytest.raises(ValueError, match='seed'):
        module.main()
    assert not launched and not (tmp_path / 'results').exists()
