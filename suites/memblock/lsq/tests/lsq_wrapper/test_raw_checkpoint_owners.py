import pytest

from lsqverify.load_raw_owners import trace


@pytest.mark.parametrize('target',range(56))
async def test_original_RAW_owner_source_pipeline_rollback_Store_bytes_and_refetch(lsq,tmp_path,target):
    await trace(lsq,tmp_path/'load-raw-owner-witness.json',target,wrapper=True)
