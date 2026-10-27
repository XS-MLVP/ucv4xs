"""Public full-width payload lifetimes through the real PSQ hierarchy."""
from lsqverify.psq.actor import PsqActor
from lsqverify.store_payload import parent_pool


async def test_all_slots_full_width_high_low_payload_lifetimes(psq_full, tmp_path):
    await parent_pool(psq_full, PsqActor(psq_full, seed=0x6620), "physical_store_queue", tmp_path)
