from lsqverify.store_queue.actor import StoreActor
from lsqverify.sq_scalar_reservation import store_trace


async def test_interface_128_scalar_reservation_older_branch_cancel_and_exact_new_UIDs(sq,tmp_path):
    await store_trace(sq,StoreActor(sq,seed=0x12861),tmp_path/"sq-scalar-reservation-witness.json")
