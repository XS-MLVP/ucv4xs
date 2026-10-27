"""Feasibility from genuine owned events, not actual DUT or coverage credit."""
from copy import deepcopy
from dataclasses import replace

import pytest

from bpuverify.bpu.checker.neighbor_migration import NeighborMigrationChecks
from bpuverify.bpu.model.pipeline import Redirect
from bpuverify.bpu.model.tage.asymmetric_retirement import (
    SOURCE_COUNT, INPUT_NAMES, OUTCOMES, SERVICE_IDENTITIES, PRELUDE_PLAN, FINAL_PLAN, expected_profile)
from bpuverify.bpu.model.tage.neighbor_migration import PC, HISTORY_PATHS
from bpuverify.bpu.model.tage.dual_migration import POSITIONS
from bpuverify.bpu.model.tage.service import STREAM_PC, learning_inflight, pending_plan
from bpuverify.tage.model.semantic import coordinate
from tests.bpu.scoreboard.test_neighbor_migration import fixture
from tests.bpu.scoreboard.test_dual_migration import source
from tests.bpu.scoreboard.test_direction_service import via, streaming_query
from tests.bpu.scoreboard.test_direction_forwarding import resolution
from tests.bpu.scoreboard.test_direction_sources import quiet


class ThreeOriginalSources(NeighborMigrationChecks):
    source_count = SOURCE_COUNT


def prepare_model(*, initial_pc=None):
    checks, (model, event, anchor), _ = fixture(initial_pc=initial_pc, checks_type=ThreeOriginalSources)
    original = via(model, event, anchor, HISTORY_PATHS['original'])
    model.advance(replace(quiet(model, event), feedback=resolution(original, OUTCOMES[1])))
    quiet(model, event)
    target = via(model, event, anchor, HISTORY_PATHS['original'])
    neighbor = via(model, event, anchor, HISTORY_PATHS['neighbor'])
    for name, path in HISTORY_PATHS.items():
        actual = via(model, event, anchor, path)
        assert checks.profile(source(model, actual, 50000)) == expected_profile(name, serviced=False)
    inputs = (checks.sources[0].token, neighbor, target, checks.sources[1].token, checks.sources[2].token)
    assert len({id(t.history) for t in inputs}) == len(INPUT_NAMES) == 5
    return checks, model, event, anchor, inputs


def concrete_plan(checks, model, inputs, plan):
    identities = {}
    for prefix, token in (('target', inputs[0]), ('neighbor', inputs[1])):
        read = model.sources.snapshot(token).read
        row, raw = coordinate(PC, read.context, 3)[1:]
        for name, position in zip(('a', 'b'), POSITIONS, strict=True):
            identities[prefix + '-' + name] = dict(row=row, valid=1, tag=raw ^ position)
    return tuple(tuple(dict(identities[name], counter=counter) for name, counter in owner) for owner in plan)


@pytest.mark.parametrize('initial_pc', (None, PC + 0x40), ids=('normal-boot', 'different-owned-boot'))
def test_normal_single_owner_pressure_creates_different_logical_service_orders_without_state_seeds(initial_pc):
    checks, model, event, anchor, inputs = prepare_model(initial_pc=initial_pc)
    frozen = tuple(deepcopy(model.sources.defined_metadata(t)) for t in inputs)
    model.advance(replace(quiet(model, event), redirect=Redirect(anchor.history, anchor.pc + 4, STREAM_PC, True)))
    for _ in range(8):
        model.advance(event)
    for first, last, expected in ((0, 3, PRELUDE_PLAN), (3, 5, FINAL_PLAN)):
        for token, outcomes in zip(inputs[first:last], OUTCOMES[first:last], strict=True):
            request = resolution(token, outcomes)
            assert not model.sources.feedback_for(request).reread
            model.advance(replace(event, feedback=request))
        for _ in range(16):
            model.advance(event)
            if not learning_inflight(model.sources.tage):
                break
        assert pending_plan(model.sources.tage, 3, PC % 4) == concrete_plan(checks, model, inputs, expected)
    assert SERVICE_IDENTITIES[0] != SERVICE_IDENTITIES[1]
    for name, path in HISTORY_PATHS.items():
        middle = streaming_query(model, event, anchor.history, path, anchor.pc + 4)
        token = streaming_query(model, event, middle.history, PC, path + 4)
        assert checks.profile(source(model, token, 51000)) == expected_profile(name, serviced=False)
    before = model.sources.tage.commits
    quiet(model, event)
    assert model.sources.tage.commits - before == 4
    for name, path in HISTORY_PATHS.items():
        actual = via(model, event, anchor, path)
        assert checks.profile(source(model, actual, 52000)) == expected_profile(name, serviced=True)
    assert tuple(model.sources.defined_metadata(t) for t in inputs) == frozen


def test_owner_orders_form_a_bijection_of_four_logical_results_not_equal_ordinal_pairs():
    assert len({name for owner in SERVICE_IDENTITIES for name in owner}) == 4
    assert all(a.split('-')[0] != b.split('-')[0] for a, b in zip(*SERVICE_IDENTITIES, strict=True))


@pytest.mark.parametrize('name', ('unknown', 'physical-rank-2'))
def test_unreviewed_physical_labels_do_not_create_history_requirements(name):
    with pytest.raises(ValueError, match='undeclared'):
        expected_profile(name, serviced=True)
