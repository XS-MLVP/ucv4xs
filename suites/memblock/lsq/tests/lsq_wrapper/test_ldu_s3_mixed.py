"""All original seeds/kinds, corrected native S3 writeback/metadata relation."""
import pytest

from .ldu_s3_owners import LduS3MixedOwners


@pytest.mark.parametrize("seed",range(0x7100,0x7108))
async def test_LDU_S3_source_original_eight_seeds_full_kinds_errors_recovery_and_fair(lsq,seed):
    await LduS3MixedOwners(lsq,seed).run()
