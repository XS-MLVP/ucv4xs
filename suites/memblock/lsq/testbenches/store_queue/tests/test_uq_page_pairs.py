from suites.memblock.lsq.testbenches.store_queue.env.actor import StoreActor
from suites.memblock.lsq.testbenches.unalign.model.uq_page_pairs import parent_pairs


async def test_actual_paired_second_pages_full_PA_bits_and_normal_reuse(sq, tmp_path):
    await parent_pairs(sq, StoreActor(sq, seed=0x6651), "store_queue", tmp_path)
