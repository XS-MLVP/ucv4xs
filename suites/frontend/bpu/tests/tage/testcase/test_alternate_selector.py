"""Check high-confidence MainBTB fallback and a correct training outcome."""

from __future__ import annotations

import pytest

from bpuverify.tage.transaction.types import TageTraining
from bpuverify.tage.coverage.catalog import tage_base_conf_coverage_model
from bpuverify.tage.coverage.catalog import write_tage_base_conf_coverage
from bpuverify.tage.case.definitions import PC
from bpuverify.tage.case.definitions import POSITION
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature("BPU-TAGE-012")
async def test_high_confidence_base_and_weak_provider_remain_consistent(tage_agent):
    await tage_agent.reset()
    coverage = tage_base_conf_coverage_model()
    cold = await tage_agent.predict(PC, POSITION, 0, base_conf=1)
    assert cold.meta["hasProvider"] == 0
    assert cold.meta["altConf"] == 1

    await tage_agent.train(TageTraining(PC, POSITION, 1, 0, cold.meta))
    low = await tage_agent.predict(PC, POSITION, 0, base_conf=0)
    assert low.meta["hasProvider"] == 1
    assert low.meta["altConf"] == 0
    assert low.meta["useProvider"] == 0
    coverage.sample({"base_conf": 0, "alt_conf": low.meta["altConf"]})

    weak = await tage_agent.predict(PC, POSITION, 0, base_conf=1)
    assert weak.meta["hasProvider"] == 1
    assert weak.meta["providerTableIdx"] == 0
    assert weak.meta["hasAlt"] == 0, weak.meta
    assert weak.meta["altConf"] == 1
    assert weak.meta["providerTakenCtr_value"] == 4
    assert weak.meta["altOrBasePred"] == 0
    assert weak.meta["useProvider"] == 0
    assert weak.valid == 0  # Bits are unspecified when there is no alternate.
    coverage.sample({"base_conf": 1, "alt_conf": weak.meta["altConf"]})

    # A correct base prediction uses the supplied prediction metadata and
    # keeps the weak provider on the fallback path.
    await tage_agent.train(
        TageTraining(
            PC, POSITION, 0, 0, weak.meta,
            mispredict=0,
            base_counter_value=0,
        )
    )
    aged = await tage_agent.predict(PC, POSITION, 0, base_conf=1)
    assert aged.meta["hasProvider"] == 1
    assert aged.meta["providerTakenCtr_value"] == 3
    assert aged.meta["altConf"] == 1
    assert aged.meta["useProvider"] == 0
    assert aged.valid == 0
    coverage.assert_coverage(100.0)
    write_tage_base_conf_coverage(coverage, REPO_ROOT)
