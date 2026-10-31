import pytest

from suites.memblock.lsq.store_queue.actor import StoreActor
from suites.memblock.lsq.vsq_recovery import store_windows


@pytest.mark.parametrize("delay", range(3))
async def test_retired_prefix_phase_windows_keep_old_bytes_and_complete_new_UIDs(sq, tmp_path, delay):
    await store_windows(sq, StoreActor(sq, seed=0x6670 + delay), delay,
                        tmp_path / "vsq-release-walk-witness.json")
