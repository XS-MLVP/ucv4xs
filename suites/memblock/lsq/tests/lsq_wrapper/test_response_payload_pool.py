from suites.memblock.lsq.load_response_payload import parent_trace


async def test_each_real_mid_response_bits_source_S3_fault_recovery_and_final_completion(lsq,tmp_path):
    await parent_trace(lsq,tmp_path/"load-response-payload-witness.json",wrapper=True)
