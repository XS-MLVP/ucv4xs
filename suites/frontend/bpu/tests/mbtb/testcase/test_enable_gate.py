"""MainBTB enable gate applies independently to lookup and training."""

from __future__ import annotations

import pytest

from bpuverify.mbtb.checker.assertions import assert_miss
from bpuverify.mbtb.checker.assertions import assert_vector_hit
from bpuverify.mbtb.case.definitions import DIRECT
from bpuverify.mbtb.case.definitions import INDIRECT
from bpuverify.mbtb.case.enable_scenarios import observe_lookup_gate
from bpuverify.mbtb.case.enable_scenarios import observe_training_gate


@pytest.mark.feature("BPU-MBTB-010")
async def test_disable_holds_lookup_pipeline_until_reenabled(mbtb_agent):
    observed = await observe_lookup_gate(mbtb_agent)
    assert_miss(observed.held)
    assert observed.disabled == observed.held, observed
    assert not any(
        item["rawHit"] for bank in observed.disabled.meta_entries for item in bank
    ), observed
    assert_vector_hit(observed.restored, DIRECT)


@pytest.mark.feature("BPU-MBTB-011")
async def test_disable_blocks_training_without_losing_existing_entry(mbtb_agent):
    observed = await observe_training_gate(mbtb_agent)
    assert_vector_hit(observed.disabled_update, INDIRECT)
    assert_vector_hit(observed.enabled_update, observed.changed)
