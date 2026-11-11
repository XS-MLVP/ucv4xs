"""Public full-width payload lifetimes through real VSQ + PSQ connections."""
from suites.memblock.lsq.testbenches.store_queue.env.actor import StoreActor
from suites.memblock.lsq.testbenches.store_queue.model.store_payload import parent_pool


async def test_all_slots_full_width_high_low_payload_lifetimes(sq, tmp_path):
    await parent_pool(sq, StoreActor(sq, seed=0x6621), "store_queue", tmp_path)
