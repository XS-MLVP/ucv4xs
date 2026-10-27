"""Real PSQ strict address holes and exact-target controls before completion."""
from lsqverify.psq.actor import PsqActor
from lsqverify.store_strict import parent_lifetimes


async def test_strict_hole_precise_control_and_real_STA_four_lifetimes(psq_full, tmp_path):
    await parent_lifetimes(psq_full, PsqActor(psq_full, seed=0x6630), "physical_store_queue", tmp_path)
