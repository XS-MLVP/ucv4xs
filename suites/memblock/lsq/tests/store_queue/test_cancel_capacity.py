from lsqverify.store_queue.actor import StoreActor
from lsqverify.vsq_cancel_capacity import store_trace


async def test_real_cancel_capacity_old_bytes_and_every_new_UID_normal_consumption(sq, tmp_path):
    await store_trace(sq, StoreActor(sq, seed=0x6681), tmp_path / "vsq-cancel-capacity-witness.json")


async def test_unlicensed_head_cancel_capacity_every_new_UID_normal_consumption(sq, tmp_path):
    await store_trace(sq, StoreActor(sq, seed=0x6681), tmp_path / "vsq-cancel-capacity-witness.json", head_permit=False)
