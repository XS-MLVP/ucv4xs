from suites.memblock.lsq.psq.actor import PsqActor
from suites.memblock.lsq.store_prefix import parent_windows


async def test_nonfull_wrapped_exclusive_prefix_and_byte_offsets(psq_full, tmp_path):
    await parent_windows(psq_full, PsqActor(psq_full, seed=0x6640), "physical_store_queue", tmp_path)
