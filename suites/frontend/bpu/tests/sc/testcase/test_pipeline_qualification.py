"""SC's S2 qualification belongs to each response, not the next lookup."""

from __future__ import annotations

import pytest

from bpuverify.sc.coverage.catalog import sc_pipeline_coverage_model
from bpuverify.sc.coverage.catalog import write_sc_pipeline_coverage
from bpuverify.sc.checker.assertions import learn
from bpuverify.sc.case.definitions import PC
from bpuverify.sc.case.definitions import POSITION
from bpuverify.sc.case.definitions import TAGE_COUNTER
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-SC-009")
async def test_interleaved_s2_qualification_keeps_response_alignment(sc_agent):
    coverage = sc_pipeline_coverage_model()
    await sc_agent.reset()
    learned = await learn(sc_agent, 1)
    assert (learned.used, learned.taken) == (1, 1)

    qualifications = (
        ("valid_conditional", {}, 1, 1),
        ("mbtb_miss", {"mbtb_valid": 0}, 0, 1),
        ("provider_invalid", {"provider_valid": 0}, 0, 0),
        ("nonconditional", {"branch_type": 2}, 0, 1),
        ("valid_conditional", {}, 1, 1),
        ("mbtb_miss", {"mbtb_valid": 0}, 0, 1),
    )
    transfers = [
        sc_agent.submit_predict(PC, POSITION, TAGE_COUNTER, **overrides)
        for _, overrides, _, _ in qualifications
    ]
    await sc_agent.drain_predictions()
    predictions = [await transfer for transfer in transfers]
    used = [expected for _, _, expected, _ in qualifications]
    provider_valid = [expected for _, _, _, expected in qualifications]
    assert [prediction.used for prediction in predictions] == used
    assert [prediction.meta["useScPred"][0] for prediction in predictions] == used
    assert [prediction.meta["tagePredValid"][0] for prediction in predictions] == provider_valid
    accepted = [transfer.accepted_event.tick for transfer in transfers]
    assert accepted == list(range(accepted[0], accepted[0] + 2 * len(transfers), 2))
    names = [name for name, _, _, _ in qualifications]
    for previous, current in zip(names, names[1:]):
        coverage.sample({"qualification_transition": f"{previous}->{current}"})
    coverage.assert_coverage(100.0)
    write_sc_pipeline_coverage(coverage, REPO_ROOT)
