"""Test discovery must not invalidate earlier execution/coverage evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from bpuverify.common.pytest import features as pytest_features


def test_collect_only_returns_before_accessing_execution_evidence(tmp_path):
    config = SimpleNamespace(option=SimpleNamespace(collectonly=True), rootpath=tmp_path)
    pytest_features.pytest_sessionfinish(SimpleNamespace(config=config), exitstatus=0)
    pytest_features.pytest_sessionfinish(SimpleNamespace(config=config), exitstatus=2)
    assert list(tmp_path.iterdir()) == []


def test_collect_only_summary_does_not_claim_tests_executed():
    lines = []
    reporter = SimpleNamespace(
        config=SimpleNamespace(option=SimpleNamespace(collectonly=True)),
        write_line=lines.append,
    )
    pytest_features.pytest_terminal_summary(reporter)
    assert lines == ["collection only; existing BPU verification reports preserved"]


def test_real_pytest_collection_preserves_normal_execution_reports(tmp_path):
    (tmp_path/"plan.json").write_text(json.dumps({"features": [{"id": "DEMO-001"}]}))
    config = tmp_path/"pytest.ini"
    config.write_text(
        "[pytest]\n"
        "toffee_feature_plan = plan.json\n"
        "toffee_feature_report = results/feature-points.json\n"
        "markers = feature(id): verification point\n"
    )
    test = tmp_path/"test_demo.py"
    test.write_text(
        "import pytest\n"
        "@pytest.mark.feature('DEMO-001')\n"
        "def test_demo():\n"
        "    assert True\n"
    )
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    env["PYTHONPATH"] = os.pathsep.join((str(root), env.get("PYTHONPATH", "")))
    command = [sys.executable, "-m", "pytest", "-q", "-c", str(config),
               "-p", 'bpuverify.common.pytest.features', str(test)]
    published = (tmp_path/"results/feature-points.json", tmp_path/"results/rtl-coverage-manifest.json")
    published[0].parent.mkdir()
    for path in published:
        path.write_text('preserved full-regression evidence\n')
    original = [path.read_bytes() for path in published]
    normal = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert normal.returncode == 0, normal.stdout + normal.stderr
    runs = list((tmp_path/'results').glob('pytest-*'))
    assert len(runs) == 1
    run, = runs
    paths = (run/"feature-points.json", run/"rtl-coverage-manifest.json")
    previous = [path.read_bytes() for path in paths]
    feature_report = json.loads(previous[0])
    assert feature_report["summary"]["passed"] == feature_report["summary"]["executed"] == 1
    assert json.loads(previous[1])["pytest_exitstatus"] == 0
    collected = subprocess.run(command + ["--collect-only"], cwd=tmp_path, env=env,
                               capture_output=True, text=True, timeout=30)
    assert collected.returncode == 0, collected.stdout + collected.stderr
    assert "reports preserved" in collected.stdout
    assert [path.read_bytes() for path in paths] == previous
    assert [path.read_bytes() for path in published] == original
    assert list((tmp_path/'results').glob('pytest-*')) == runs

    test.write_text("def test_demo():\n    assert False, 'ordinary test failure'\n")
    failed = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert len(list((tmp_path/'results').glob('pytest-*'))) == 2
    assert [path.read_bytes() for path in paths] == previous
    assert [path.read_bytes() for path in published] == original
