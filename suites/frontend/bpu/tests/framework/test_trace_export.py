"""Default-off exports must not weaken checking or functional coverage."""
import ast
import asyncio
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from suites.frontend.bpu.runtime.trace import dump_trace
from suites.frontend.bpu.runtime.trace import trace_exports


@pytest.mark.parametrize("value", [None, {}, [], object(), {"bad": object()}])
def test_default_off_does_not_serialize_or_create_directories(tmp_path, value):
    assert dump_trace(tmp_path / "absent" / "trace.json", value) is None
    assert list(tmp_path.iterdir()) == []


def test_default_off_does_not_even_resolve_the_path():
    class BadPath:
        def __fspath__(self):
            raise AssertionError("disabled diagnostics resolved a filesystem path")
    assert dump_trace(BadPath(), object()) is None


@pytest.mark.parametrize("value", [None, {}, [], {"frames": [dict(tick=1, state=[0]*1024)],
                                                  "unicode": "按需轨迹", "flag": True}])
@pytest.mark.parametrize("suffix", [".json", ".json.gz"])
def test_opt_in_is_complete_compressed_json(tmp_path, value, suffix):
    with trace_exports():
        path = dump_trace(tmp_path / ("trace" + suffix), value)
    assert path.name == "trace.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        assert json.load(stream) == value
    assert list(tmp_path.iterdir()) == [path]


def test_explicit_default_serializer(tmp_path):
    class Custom:
        def __str__(self):
            return "custom-state"
    with trace_exports():
        path = dump_trace(tmp_path / "trace.json", {"custom": Custom()}, default=str)
    with gzip.open(path, "rt") as stream:
        assert json.load(stream) == {"custom": "custom-state"}


def test_existing_trace_is_not_replaced(tmp_path):
    with trace_exports():
        path = dump_trace(tmp_path / "trace.json", {"first": 1})
        before = path.read_bytes()
        with pytest.raises(FileExistsError):
            dump_trace(tmp_path / "trace.json", {"second": 2})
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_stream_failure_leaves_no_partial_trace(tmp_path):
    with trace_exports():
        with pytest.raises(TypeError):
            dump_trace(tmp_path / "trace.json", {"valid": list(range(20)), "bad": object()})
    assert list(tmp_path.iterdir()) == []


def test_context_is_restored_when_checker_raises(tmp_path):
    with pytest.raises(AssertionError, match="real checker failed"):
        with trace_exports():
            raise AssertionError("real checker failed")
    assert dump_trace(tmp_path / "trace.json", object()) is None


def test_nested_disable_preserves_outer_request(tmp_path):
    with trace_exports():
        with trace_exports(False):
            assert dump_trace(tmp_path / "disabled.json", object()) is None
        assert dump_trace(tmp_path / "enabled.json", {}) is not None
    assert dump_trace(tmp_path / "after.json", object()) is None


@pytest.mark.parametrize("invalid", [None, 0, 1, "false", "true", [], {}])
def test_no_truthy_implicit_enable(invalid):
    with pytest.raises(TypeError):
        with trace_exports(invalid):
            pass


async def test_concurrent_tasks_have_independent_diagnostic_contexts(tmp_path):
    async def writer(enabled, name):
        with trace_exports(enabled):
            await asyncio.sleep(0)
            return dump_trace(tmp_path / name, {"frames": [1, 2, 3]})
    enabled = asyncio.create_task(writer(True, "enabled.json"))
    disabled = asyncio.create_task(writer(False, "disabled.json"))
    assert await enabled is not None
    assert await disabled is None
    assert {path.name for path in tmp_path.iterdir()} == {"enabled.json.gz"}


TRACE_WRITERS = [
    'utage/case/partial_wrap_scenario.py',
    'bpu/case/phr_recovery.py',
    'bpu/case/phr_direction_repair.py',
    'bpu/case/phr_taken_wrap.py',
    'utage/case/useful_address_scenario.py',
    'bpu/case/bypass/alternate_history.py',
    'abtb/env/state/counter.py',
    'bpu/case/bypass/policy_program.py',
    'bpu/case/bypass/force.py',
    'bpu/case/bypass/two_program.py',
    'bpu/case/bypass/history.py',
    'abtb/env/state/priority.py',
    'bpu/case/bypass/aging.py',
    'abtb/env/state/replacer.py',
    'bpu/case/bypass/lower_ring.py',
    'abtb/env/state/writebuffer.py',
    'bpu/case/sc/scenarios.py',
    'bpu/case/abtb/alias.py',
    'bpu/case/sc/role_scenarios.py',
    'bpu/case/abtb/final_not_taken.py',
    'bpu/case/sc/history_training.py',
    'bpu/case/bypass/sram.py',
    'bpu/case/sc/nonzero_scenarios.py',
    'bpu/case/bypass/natural.py',
    'bpu/case/abtb/natural.py',
    'bpu/case/bypass/force_seed.py',
    'bpu/case/ras/cases.py'
]


# Keep historical parameter IDs stable; only the actual source location moved.
@pytest.mark.parametrize("relative", TRACE_WRITERS, ids=lambda relative: 'bpuverify/'+relative)
def test_every_scenario_uses_the_optional_sink(relative):
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / relative).read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert sum(isinstance(node.func, ast.Name) and node.func.id == "dump_trace"
               for node in calls) == 1
    assert not any(isinstance(node.func, ast.Attribute) and node.func.attr == "write_text"
                   for node in calls)
    assert not any(isinstance(node.func, ast.Name) and node.func.id == "write_trace"
                   for node in calls)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("workers", [0, 2])
def test_real_pytest_flag_reaches_serial_and_xdist_workers(tmp_path, enabled, workers):
    root = Path(__file__).resolve().parents[2]
    test = tmp_path / "test_demo.py"
    test.write_text(
        "import pytest\nfrom pathlib import Path\nfrom suites.frontend.bpu.runtime.trace import dump_trace\n@pytest.mark.parametrize('item', [0, 1])\ndef test_demo(item):\n    target = Path(__file__).with_name(f'trace-{item}.json')\n    dump_trace(target, {'tick': item, 'value': [0, 1]})\n"
    )
    config = tmp_path / "pytest.ini"
    config.write_text("[pytest]\n")
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
           "PYTHONDONTWRITEBYTECODE": "1"}
    env["PYTHONPATH"] = os.pathsep.join((str(root), env.get("PYTHONPATH", "")))
    command = [sys.executable, "-m", "pytest", "-q", "-c", str(config),
               "-p", "no:cacheprovider", "-p", 'suites.frontend.bpu.pytest_plugins.artifacts',
               "--basetemp", str(tmp_path / "pytest-tmp")]
    if workers:
        command += ["-p", "xdist.plugin", "-n", str(workers), "--max-worker-restart=0"]
    if enabled:
        command += ["--dump-trace"]
    completed = subprocess.run(command + [str(test)], env=env, cwd=tmp_path,
                               capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "2 passed" in completed.stdout
    traces = list(tmp_path.glob("trace-*.json.gz"))
    assert len(traces) == (2 if enabled else 0)
    assert not list(tmp_path.glob("trace-*.json"))
