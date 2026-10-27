"""The public regression entry point always uses the production owner."""
import sys

import pytest

from tests import run_all


@pytest.mark.parametrize('arguments', [[], ['--workers=1'], ['--workers=8', '--run-dir=results/new-run'],
                                     ['--workers=8', '--select', 'tests/tage']])
@pytest.mark.parametrize('status', [0, 1, 9])
def test_regression_forwards_options_and_exitstatus(tmp_path, monkeypatch, arguments, status):
    monkeypatch.setattr(run_all, 'ROOT', tmp_path)
    monkeypatch.setenv('PYTHONPATH', '/existing/runtime')
    calls = []

    def call(command, **kwargs):
        calls.append((command, kwargs))
        return status

    monkeypatch.setattr(run_all.subprocess, 'call', call)
    assert run_all.main(arguments) == status
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command == [sys.executable, str(tmp_path / 'tools/refresh_coverage.py'), *arguments]
    assert kwargs['cwd'] == tmp_path
    assert kwargs['env']['PYTHONPATH'].split(run_all.os.pathsep) == [
        str(tmp_path), '/existing/runtime',
    ]


def test_regression_command_line_arguments_reach_owner(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['tests/run_all.py', '--workers=4'])
    calls = []
    monkeypatch.setattr(run_all.subprocess, 'call', lambda command, **kwargs: calls.append(command) or 0)
    assert run_all.main() == 0
    assert calls[0][-1] == '--workers=4'
