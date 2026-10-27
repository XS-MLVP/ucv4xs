from lsqverify.load_response_payload import parent_trace


async def test_each_real_mid_response_bits_source_S3_and_final_LQ_completion(lq,tmp_path):
    await parent_trace(lq,tmp_path/"load-response-payload-witness.json")
