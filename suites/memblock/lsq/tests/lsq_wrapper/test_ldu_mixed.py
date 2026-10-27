"""Original8 seeds/full kinds; new LDU scheduler is not an admission claim."""
import pytest

from .ldu_mixed_owners import LduMixedOwners


@pytest.mark.parametrize("seed",range(0x7100,0x7108))
async def test_LDU_pipeline_original_eight_seeds_all_kinds_errors_recovery_and_fair_obligations(lsq,seed):
    await LduMixedOwners(lsq,seed).run()
