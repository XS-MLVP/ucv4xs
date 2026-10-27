"""Real VSQ/PSQ strict response identities through normal consume/reuse."""
from lsqverify.store_queue.actor import StoreActor
from lsqverify.store_strict import parent_lifetimes


async def test_strict_hole_precise_control_and_real_STA_four_lifetimes(sq, tmp_path):
    await parent_lifetimes(sq, StoreActor(sq, seed=0x6631), "store_queue", tmp_path)
