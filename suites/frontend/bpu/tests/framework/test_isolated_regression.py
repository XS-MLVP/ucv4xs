"""Aggregation preserves checks and provenance; it never sums native tables."""
from copy import deepcopy
from threading import Event, Thread

import pytest

from suites.frontend.bpu.coverage import rtl
from suites.frontend.bpu.pytest_plugins.points import make_report
from tools.dut_isolated_regression import WorkerBudget, combine_features, worker_allocation


@pytest.mark.parametrize('workers,cases,domains,expected',(
    (4,8,1,4),(4,4,1,4),(4,1,1,1),(1,8,1,1),(3,8,1,3),
    (4,8,2,2),(4,8,10,2),(3,8,2,2),(4,1,2,1),(1,8,10,1)))
def test_single_domain_uses_its_requested_budget_without_changing_multi_domain_sharing(workers,cases,domains,expected):
    assert worker_allocation(workers,cases,domains)==expected


@pytest.mark.parametrize('values',((0,8,1),(4,0,1),(4,8,0),(True,8,1),(4,8,1.5)))
def test_invalid_domain_worker_allocation_cannot_bypass_the_budget(values):
    with pytest.raises(ValueError,match='positive'):
        worker_allocation(*values)


@pytest.mark.parametrize('slots', (-1, 0, True, 1.5))
def test_invalid_worker_budget_is_not_a_request_for_unbounded_parallelism(slots):
    with pytest.raises(ValueError, match='positive'):
        WorkerBudget(slots)


@pytest.mark.parametrize('count', (-1, 0, 4, True, 1.5))
def test_invalid_whole_allocations_are_rejected(count):
    with pytest.raises(ValueError, match='allocation'):
        WorkerBudget(3).acquire(count)


def test_worker_allocations_cannot_deadlock_by_reserving_partial_slots():
    budget = WorkerBudget(3)
    budget.acquire(2)
    waiting, done = Event(), Event()

    def another_domain():
        waiting.set()
        budget.acquire(2)
        assert budget.available == 1
        budget.release(2)
        done.set()

    thread = Thread(target=another_domain)
    thread.start()
    try:
        assert waiting.wait(2)
        assert budget.available == 1
    finally:
        budget.release(2)
    thread.join(2)
    assert not thread.is_alive() and done.is_set() and budget.available == 3


def test_a_stopped_budget_cannot_launch_pending_domains():
    budget = WorkerBudget(2)
    budget.stop()
    with pytest.raises(RuntimeError, match='stopped'):
        budget.acquire(1)


def test_worker_slots_cannot_be_released_twice():
    budget = WorkerBudget(2)
    with pytest.raises(ValueError, match='duplicate'):
        budget.release(1)


def feature_data():
    point = dict(id='BPU-DEMO-001', title='independent logical learning', component='demo', description='demo')
    nodes = ('tests/bpu/testcase/test_x.py::test_a', 'tests/ras/testcase/test_x.py::test_b')
    index = dict(cases=[dict(nodeid=node, features=[point['id']]) for node in nodes])
    reports = [make_report([dict(point, tests=[dict(nodeid=node, status=status)], status=status)],
                          integrity_errors=[]) for node, status in zip(nodes, ('PASS', 'XFAIL'))]
    return dict(features=[point]), index, reports, dict(zip(nodes, ('PASS', 'XFAIL')))


def test_feature_point_aggregation_keeps_strict_xfail_and_every_original_test():
    plan, index, reports, tests = feature_data()
    result = combine_features(plan, index, reports, tests)
    assert result['features'][0]['status'] == 'PASS'
    assert {row['nodeid']: row['status'] for row in result['features'][0]['tests']} == tests


@pytest.mark.parametrize('fault', ('duplicate', 'missing', 'verdict', 'unknown-point', 'definition', 'integrity'))
def test_aggregation_cannot_repair_missing_or_changed_feature_evidence(fault):
    plan, index, reports, tests = deepcopy(feature_data())
    if fault == 'duplicate': reports.append(reports[0])
    elif fault == 'missing': reports.pop()
    elif fault == 'verdict': tests[next(iter(tests))] = 'FAIL'
    elif fault == 'unknown-point': reports[0]['features'][0]['id'] = 'unknown'
    elif fault == 'definition': reports[0]['features'][0]['title'] = 'changed'
    else: reports[0]['integrity_errors'] = ['missing phase']
    if fault in ('unknown-point', 'definition'):
        old = reports[0]
        reports[0] = make_report(old['features'], integrity_errors=old['integrity_errors'])
    with pytest.raises(ValueError):
        combine_features(plan, index, reports, tests)


@pytest.mark.parametrize('dut', ('bpu', 'ras', 'tage', 'utage'))
def test_report_relocation_requires_equal_full_relative_rtl_sources(tmp_path, monkeypatch, dut):
    old = tmp_path / 'original/rtl' / dut / 'Predictor.sv'
    new_root = tmp_path / 'candidate'
    new = new_root / 'rtl' / dut / old.name
    old.parent.mkdir(parents=True)
    new.parent.mkdir(parents=True)
    old.write_text('module Predictor; endmodule\n')
    new.write_bytes(old.read_bytes())
    monkeypatch.setattr(rtl, 'ROOT', new_root)
    assert rtl._source_path(str(old), dut) == new
    new.write_text('module Different; endmodule\n')
    with pytest.raises(ValueError, match='content changed'):
        rtl._source_path(str(old), dut)


def test_source_with_equal_basename_but_different_hierarchy_is_not_remapped(tmp_path, monkeypatch):
    old = tmp_path / 'unrelated/bpu/Predictor.sv'
    new_root = tmp_path / 'candidate'
    new = new_root / 'rtl/bpu/Predictor.sv'
    old.parent.mkdir(parents=True)
    new.parent.mkdir(parents=True)
    old.write_text('module Predictor; endmodule\n')
    new.write_bytes(old.read_bytes())
    monkeypatch.setattr(rtl, 'ROOT', new_root)
    assert rtl._source_path(str(old), 'bpu') == old
