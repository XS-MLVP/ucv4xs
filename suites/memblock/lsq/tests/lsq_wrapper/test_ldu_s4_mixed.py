"""Eight original full-kind/error/recovery seeds, S4 TLB source corrected."""
import pytest

from .ldu_s4_mixed_owners import LduS4MixedOwners


@pytest.mark.parametrize("seed",range(0x7100,0x7108))
async def test_LDU_S4_original_eight_seeds_full_kinds_errors_recovery_and_fair(lsq,seed):
    await LduS4MixedOwners(lsq,seed).run()
