from suites.memblock.lsq.vsq_cancel_capacity import leaf_trace


async def test_real_cancel_count_capacity_and_every_virtual_slot_new_UID(vsq, tmp_path):
    await leaf_trace(vsq, tmp_path / "vsq-cancel-capacity-witness.json")
