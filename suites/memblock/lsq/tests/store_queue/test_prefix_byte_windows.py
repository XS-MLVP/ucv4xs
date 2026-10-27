from lsqverify.store_queue.actor import StoreActor
from lsqverify.store_prefix import parent_windows


async def test_nonfull_wrapped_exclusive_prefix_and_byte_offsets(sq, tmp_path):
    await parent_windows(sq, StoreActor(sq, seed=0x6641), "store_queue", tmp_path)
