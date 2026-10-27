"""Full domain first: ordinary FAILs are retained, never replaced by controls."""
import pytest

from .mixed_owners import MixedOwners


@pytest.mark.parametrize("seed", (0x7100, 0x7101, 0x7102, 0x7103, 0x7104, 0x7105, 0x7106, 0x7107))
async def test_one_global_rob_full_mixed_domain_original_obligations_and_fair_drain(lsq, seed):
    await MixedOwners(lsq, seed).run()
