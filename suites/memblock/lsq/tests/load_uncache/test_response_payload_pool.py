from suites.memblock.lsq.load_response_payload import uncache_trace


async def test_each_real_mid_response_bits_errors_and_original_public_consumption(load_uncache,tmp_path):
    await uncache_trace(load_uncache,tmp_path/"load-response-payload-witness.json")
