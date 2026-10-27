from lsqverify.vsq_retire_known import leaf_trace


async def test_known_one_64_16_one_flow_batches_retire_then_physically_consume(vsq, tmp_path):
    await leaf_trace(vsq, tmp_path / "vsq-retire-known-width-witness.json")
