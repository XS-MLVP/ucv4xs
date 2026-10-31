"""Full immutable physical schema and per-scenario semantic credit, without DUT."""
from types import SimpleNamespace

import pytest
from toffee import CoverageDatabase

from suites.frontend.bpu.mbtb.case.replacement_scenario import TOUCH_MODES, PHASES
from suites.frontend.bpu.mbtb.coverage.catalog import mbtb_replacement_coverage_model
from tests.mbtb.testcase import test_replacement_indices as CASE


@pytest.mark.parametrize('mode', TOUCH_MODES)
async def test_partial_export_retains_full_physical_schema_and_one_complete_semantic_rule(monkeypatch, mode):
    writes = []
    async def check(agent, coverage, index, align, upper, received_mode):
        assert (index, align, upper, received_mode) == (63, 1, 1, mode)
        for phase in PHASES:
            coverage.sample(dict(index=index, align=align, upper=upper, mode=mode, phase=phase))
    def export(group, root, *, semantic_groups):
        semantic_groups = tuple(semantic_groups)
        assert group.definition.digest == mbtb_replacement_coverage_model().definition.digest
        bins = group.report()['crosses'][0]['bins']
        assert len(bins) == 24576
        assert group.cross_coverage('all_dimensions') == pytest.approx(100 / 4096)
        assert len(semantic_groups) == 2 and all(item.coverage == 25 for item in semantic_groups)
        CoverageDatabase.from_dict(CoverageDatabase([group, *semantic_groups]).report())
        writes.append(group)
    monkeypatch.setattr(CASE, 'check_case', check)
    monkeypatch.setattr(CASE, 'write_mbtb_replacement_coverage', export)
    agent = SimpleNamespace(reference=SimpleNamespace(raise_failure=lambda: None))
    await CASE.test_indexed_replacement_shares_alias_state_and_preserves_independent_neighbors(agent, 63, 1, 1, mode)
    assert len(writes) == 1


async def test_failed_native_or_semantic_check_cannot_export_partial_pass_credit(monkeypatch):
    writes = []
    async def fail(*args):
        raise AssertionError('intentional failed replacement')
    monkeypatch.setattr(CASE, 'check_case', fail)
    monkeypatch.setattr(CASE, 'write_mbtb_replacement_coverage', lambda *args, **kwargs: writes.append(args))
    with pytest.raises(AssertionError, match='intentional failed replacement'):
        await CASE.test_indexed_replacement_shares_alias_state_and_preserves_independent_neighbors(
            object(), 0, 0, 0, 'taken_way0')
    assert writes == []
