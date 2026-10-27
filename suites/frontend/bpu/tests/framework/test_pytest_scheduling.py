"""Ordering is only a permutation, never a timeout or a selection rule."""
from types import SimpleNamespace

import pytest
from bpuverify.common.pytest.scheduling import order_tests


def item(name, *args, **kwargs):
    marker = None if not args and not kwargs else SimpleNamespace(args=args, kwargs=kwargs)
    return SimpleNamespace(nodeid=name, get_closest_marker=lambda kind: marker)


def test_long_stateful_scenarios_start_first_and_all_items_survive():
    items = [item('ordinary'), item('matrix', 800), item('aging', 1340),
             item('matrix_next', 800), item('ordinary_next'), item('zero', 0)]
    original = list(items)
    order_tests(items)
    assert [row.nodeid for row in items] == ['aging', 'matrix', 'matrix_next', 'ordinary', 'ordinary_next', 'zero']
    assert {id(row) for row in items} == {id(row) for row in original}


@pytest.mark.parametrize('fault', [True, False, -1, -0.5, float('nan'), float('inf'), -float('inf'),
                                  None, '800', [], {}, object()])
def test_invalid_hints_fail_collection_before_reordering(fault):
    items = [item('short', 1), item('long', 900), item('invalid', fault)]
    original = list(items)
    with pytest.raises(pytest.UsageError, match='estimated_runtime'):
        order_tests(items)
    assert items == original


@pytest.mark.parametrize('args,kwargs', [((1, 2), {}), ((), dict(seconds=800)), ((1,), dict(timeout=1))])
def test_hints_are_not_arbitrary_pytest_options(args, kwargs):
    with pytest.raises(pytest.UsageError):
        order_tests([item('invalid', *args, **kwargs)])


@pytest.mark.parametrize('workers', [1, 2, 8, 32])
def test_every_worker_and_serial_collection_receive_identical_order(workers):
    original = [(str(index), index % 7) for index in range(100)]
    controllers = []
    for worker in range(workers):
        items = [item(name, cost) for name, cost in original]
        order_tests(items)
        controllers.append([row.nodeid for row in items])
    assert all(nodes == controllers[0] for nodes in controllers)
    assert set(controllers[0]) == {name for name, cost in original}


def test_default_collection_order_remains_unchanged_without_hints():
    items = [item(str(index)) for index in range(10)]
    original = list(items)
    order_tests(items)
    assert items == original


def test_integer_costs_do_not_overflow_float_validation():
    items = [item('finite_float', 1.5), item('large_integer', 10 ** 400)]
    order_tests(items)
    assert [row.nodeid for row in items] == ['large_integer', 'finite_float']


def filler(name, *, fixtures=(), feature=False):
    return SimpleNamespace(nodeid=name, fixturenames=list(fixtures),
        get_closest_marker=lambda kind: object() if kind == 'feature' and feature else None)


@pytest.mark.parametrize('available', (0, 1, 2, 5))
def test_long_scenarios_have_cheap_initial_lookahead_without_losing_items(available):
    contracts = [filler(f'contract{i}') for i in range(available)]
    items = [item('medium', 500), *contracts, item('long', 900), filler('feature_case', feature=True)]
    original = list(items)
    order_tests(items)
    expected = ['long']
    if available: expected.append('contract0')
    expected.append('medium')
    if available > 1: expected.append('contract1')
    expected.extend(f'contract{i}' for i in range(2, available))
    expected.append('feature_case')
    assert [row.nodeid for row in items] == expected
    assert sorted(map(id, items)) == sorted(map(id, original))
    again = list(items)
    order_tests(items)
    assert items == again


@pytest.mark.parametrize('fixtures', (('agent',), ('bpu_agent',), ('transitive_dut',), ('dut_factory',)))
def test_dut_fixture_closure_is_never_a_contract_filler(fixtures):
    consumer = filler('native_consumer', fixtures=fixtures)
    items = [consumer, item('long', 900), item('medium', 500), filler('contract')]
    order_tests(items)
    assert [row.nodeid for row in items] == ['long', 'contract', 'medium', 'native_consumer']


def test_no_hints_preserves_original_order_even_with_contract_candidates():
    items = [filler('a'), filler('b', feature=True), filler('c')]
    original = list(items)
    order_tests(items)
    assert items == original


@pytest.mark.parametrize('has_evidence', [False, True])
def test_project_hook_orders_before_evidence_and_legacy_mapping(has_evidence):
    from bpuverify.common.pytest import features as pytest_features
    values = [item('short'), item('long', 800)]
    for value in values:
        value.iter_markers = lambda name: []
    config = SimpleNamespace(_bpu_evidence=object() if has_evidence else None,
                             _bpu_feature_nodes={}, _bpu_feature_ids=set())
    pytest_features.pytest_collection_modifyitems(config, values)
    assert [value.nodeid for value in values] == ['long', 'short']
    assert pytest_features.pytest_collection_modifyitems.pytest_impl['tryfirst']


@pytest.mark.parametrize('workers', [1, 2])
def test_real_pytest_workers_record_the_same_long_first_collection(tmp_path, workers):
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    from bpuverify.common.pytest.evidence import collection_digest

    (tmp_path / 'plan.json').write_text(json.dumps({'features': [{'id': 'ORDER-001'}]}))
    config = tmp_path / 'pytest.ini'
    config.write_text(
        '[pytest]\ntoffee_feature_plan = plan.json\n'
        'toffee_feature_report = results/features.json\n'
        'markers =\n    feature(id): point\n    estimated_runtime(seconds): scheduling hint\n')
    (tmp_path / 'test_hints.py').write_text(
        'import pytest\n'
        '@pytest.mark.feature("ORDER-001")\n'
        'def test_short(): pass\n'
        '@pytest.mark.feature("ORDER-001")\n'
        '@pytest.mark.estimated_runtime(900)\n'
        'def test_long(): pass\n'
        '@pytest.mark.feature("ORDER-001")\n'
        '@pytest.mark.estimated_runtime(500)\n'
        'def test_medium(): pass\n')
    run = tmp_path / 'results/ordered'
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    env['PYTHONPATH'] = os.pathsep.join((str(root), env.get('PYTHONPATH', '')))
    command = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
               '-p', 'bpuverify.common.pytest.features', '-c', str(config),
               '--rtl-retention=raw', f'--artifact-run={run}']
    if workers > 1:
        command.extend(('-p', 'xdist.plugin', '-n', str(workers), '--dist=load',
                        '--maxschedchunk=1', '--max-worker-restart=0'))
    child = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True,
                           text=True, timeout=30)
    assert child.returncode == 0, child.stdout + child.stderr
    evidence = json.loads((run / 'evidence.json').read_text())
    assert evidence['evidence_complete'] and not evidence['integrity_errors']
    assert evidence['test_status_counts'] == {'PASS': 3}
    assert len(evidence['workers']) == workers
    expected = ['test_hints.py::test_long', 'test_hints.py::test_medium', 'test_hints.py::test_short']
    for row in evidence['workers']:
        receipt = json.loads(Path(row['receipt']).read_text())
        assert receipt['collected_count'] == len(expected)
        assert receipt['collection_sha256'] == collection_digest(expected)


def test_real_xdist_initial_pairing_separates_the_two_long_scenarios(tmp_path):
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    from bpuverify.common.pytest.evidence import collection_digest

    (tmp_path / 'plan.json').write_text(json.dumps({'features': [{'id': 'ORDER-001'}]}))
    config = tmp_path / 'pytest.ini'
    config.write_text(
        '[pytest]\ntoffee_feature_plan = plan.json\n'
        'toffee_feature_report = results/features.json\n'
        'markers =\n    feature(id): point\n    estimated_runtime(seconds): scheduling hint\n')
    (tmp_path / 'test_pairs.py').write_text(
        'import pytest\n'
        'def test_contract0(): pass\n'
        'def test_contract1(): pass\n'
        'def test_contract2(): pass\n'
        'def test_contract3(): pass\n'
        '@pytest.mark.feature("ORDER-001")\n'
        '@pytest.mark.estimated_runtime(900)\n'
        'def test_long(): pass\n'
        '@pytest.mark.feature("ORDER-001")\n'
        '@pytest.mark.estimated_runtime(500)\n'
        'def test_medium(): pass\n')
    run = tmp_path / 'results/paired'
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    env['PYTHONPATH'] = os.pathsep.join((str(root), env.get('PYTHONPATH', '')))
    command = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
               '-p', 'bpuverify.common.pytest.features', '-p', 'xdist.plugin', '-c', str(config),
               '--rtl-retention=raw', f'--artifact-run={run}', '-n', '2', '--dist=load',
               '--maxschedchunk=1', '--max-worker-restart=0']
    child = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stdout + child.stderr
    evidence = json.loads((run / 'evidence.json').read_text())
    assert evidence['evidence_complete'] and not evidence['integrity_errors']
    assert evidence['test_status_counts'] == {'PASS': 6}
    expected = ['test_pairs.py::test_long', 'test_pairs.py::test_contract0', 'test_pairs.py::test_medium',
                'test_pairs.py::test_contract1', 'test_pairs.py::test_contract2', 'test_pairs.py::test_contract3']
    for row in evidence['workers']:
        receipt = json.loads(Path(row['receipt']).read_text())
        assert receipt['collection_sha256'] == collection_digest(expected)
    owners = {row['nodeid']: row['phases']['call']['worker'] for row in evidence['tests']}
    assert owners['test_pairs.py::test_long'] != owners['test_pairs.py::test_medium']
