from lsqverify.psq.actor import PsqActor
from lsqverify.uq_page_pairs import parent_pairs


async def test_actual_paired_second_pages_full_PA_bits_and_normal_reuse(psq_full, tmp_path):
    await parent_pairs(psq_full, PsqActor(psq_full, seed=0x6650), "physical_store_queue", tmp_path)
