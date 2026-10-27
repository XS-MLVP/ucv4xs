"""SC S2 and registered metadata must follow each MainBTB slot."""

from __future__ import annotations

import pytest

from bpuverify.sc.transaction.types import ScBaseBranch
from bpuverify.sc.coverage.catalog import sc_vector_coverage_model
from bpuverify.sc.coverage.catalog import write_sc_vector_coverage
from bpuverify.sc.checker.assertions import learn
from bpuverify.sc.case.definitions import PC
from bpuverify.sc.case.definitions import POSITION
from bpuverify.sc.case.definitions import TAGE_COUNTER
from bpuverify.common.env.paths import REPO_ROOT


def branch_layout(slot: int, *, provider_valid: int = 1):
    branches = [ScBaseBranch(1, TAGE_COUNTER, branch_type=2)]
    branches.extend([None] * (slot - 1))
    branches.append(
        ScBaseBranch(POSITION, TAGE_COUNTER, provider_valid=provider_valid)
    )
    return tuple(branches)


@pytest.mark.feature("BPU-SC-012")
async def test_nonzero_sc_slots_and_overlapped_qualification(sc_agent):
    coverage = sc_vector_coverage_model()
    await sc_agent.reset()
    learned = await learn(sc_agent, 1)
    assert (learned.used, learned.taken) == (1, 1)

    for slot in (1, 2, 3):
        observed = await sc_agent.predict_branches(PC, branch_layout(slot))
        assert len(observed.takens) == len(observed.useds) == 4
        assert observed.useds[0] == 0
        assert (observed.useds[slot], observed.takens[slot]) == (1, 1)
        assert observed.meta["useScPred"][0] == 0
        assert observed.meta["useScPred"][slot] == 1
        assert observed.meta["tagePredValid"][slot] == 1
        assert all(
            observed.meta["useScPred"][index] == 0
            for index in range(4) if index not in (0, slot)
        )
        coverage.sample({"used_slot": slot, "association": "serial"})

    layouts = ((branch_layout(2), 2, 1), (branch_layout(3, provider_valid=0), 3, 0)) * 2
    transfers = [sc_agent.submit_predict_branches(PC, branches) for branches, *_ in layouts]
    await sc_agent.drain_predictions()
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    assert accepted == list(range(accepted[0], accepted[0] + 2 * len(transfers), 2))
    assert [transfer.completed_event.tick for transfer in transfers] == [
        tick + 2 for tick in accepted
    ]
    for transfer, (branches, slot, expected_used) in zip(transfers, layouts, strict=True):
        observed = await transfer
        assert observed.useds[0] == 0
        assert observed.useds[slot] == expected_used, (branches, observed)
        assert observed.meta["useScPred"][slot] == expected_used
        assert observed.meta["tagePredValid"][slot] == expected_used
        if expected_used:
            assert observed.takens[slot] == 1
    coverage.sample({"used_slot": 2, "association": "overlap"})

    coverage.assert_coverage(100.0)
    write_sc_vector_coverage(coverage, REPO_ROOT)
