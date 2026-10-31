"""Readable version semantics, source basis and layered public use."""
import ast
import json
from pathlib import Path
from suites.frontend.bpu.bpu.coverage.service_relearning import RULES, lifetime_coverage
from suites.frontend.bpu.bpu.model.tage.service_relearning import PROGRAMS


def test_requirement_is_old_completion_versus_new_learning_not_bank_coordinates():
    contract = json.loads(Path('docs/service-relearning-contract.json').read_text())
    assert contract['existing_feature'] == 'BPU-INT-087'
    assert contract['profiles'] == [p.name for p in PROGRAMS]
    assert contract['no_bank_set_way_enumeration'] and contract['no_fixed_native_settling_delay']
    assert '旧版本' in contract['owner'] and '未执行' in contract['title']
    for ref in contract['source_chain']:
        name, line = ref.rsplit(':', 1)
        assert 0 < int(line) <= len(Path(name).read_text().splitlines())


def test_existing_capacity_and_learning_contracts_remain_registered():
    plan = json.loads(Path('verification_plan.json').read_text())
    feature = next(p for p in plan['features'] if p['id'] == 'BPU-INT-087')
    for status in ('reached', 'checked'):
        for family in ('owned-direction-capacity', 'shared-saturation', 'service-relearning'):
            assert 'kunminghu_v3.bpu.'+family+'.'+status in feature['evidence']['coverage'][status]
    assert 'bpu/checker/service_relearning.py' in feature['evidence']['checks']


def test_coverage_denominator_is_semantic_relations_times_obligations():
    for status in ('reached', 'checked'):
        group = lifetime_coverage(status)
        counts = group.report()['points'][0]['counts']
        assert len(counts) == len(PROGRAMS)*len(RULES) == 40
        assert set(counts.values()) == {0}


def test_native_case_has_no_clock_io_or_concurrency_plumbing():
    for name in ('tests/bpu/testcase/test_service_relearning.py', 'bpu/case/service_relearning.py'):
        text = Path(name).read_text()
        assert not any(s in text for s in ('FallingEdge', 'RisingEdge', 'ClockCycles', 'asyncio', 'get_', 'set_', '.Set('))
    tree = ast.parse(Path('bpu/model/tage/service_relearning.py').read_text())
    assert not any(isinstance(n, ast.Import) for n in ast.walk(tree))
