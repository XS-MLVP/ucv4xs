"""All original types/seeds, actual NoSpec/BlockBack producer, strict FAILs."""
import pytest

from .serialized_mixed_owners import SerializedMixedOwners


@pytest.mark.parametrize("seed",range(0x7100,0x7108))
async def test_serialized_CBO_full_domain_original_kinds_seeds_and_original_fair_obligations(lsq,seed):
    await SerializedMixedOwners(lsq,seed).run()
