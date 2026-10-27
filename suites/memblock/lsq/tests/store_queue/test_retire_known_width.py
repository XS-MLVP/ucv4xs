from lsqverify.store_queue.actor import StoreActor
from lsqverify.vsq_retire_known import store_trace


async def test_known_one_64_16_one_flow_real_retired_permission_and_original_bytes(sq, tmp_path):
    await store_trace(sq, StoreActor(sq, seed=0x64821), tmp_path / "vsq-retire-known-width-witness.json")
