import pytest

from lsqverify.vsq_recovery import leaf_windows


@pytest.mark.parametrize("delay", range(3))
async def test_retired_prefix_phase_windows_public_tail_and_same_slot_new_UID(vsq, tmp_path, delay):
    await leaf_windows(vsq, delay, tmp_path / "vsq-release-walk-witness.json")
