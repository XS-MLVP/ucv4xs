import pytest

from suites.memblock.lsq.load_raw_owners import trace


@pytest.mark.parametrize('target',range(56))
async def test_original_RAW_owner_full_width_checkpoint_rollback_recovery_and_refetch(lq,tmp_path,target):
    await trace(lq,tmp_path/'load-raw-owner-witness.json',target)
