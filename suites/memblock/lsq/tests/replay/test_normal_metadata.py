import pytest

from lsqverify.normal_replay_metadata import PATHS, trace


@pytest.mark.parametrize("path", PATHS)
async def test_normal_scalar_original_UID_metadata_and_live_dependency_at_every_slot(replay, tmp_path, path):
    await trace(replay, tmp_path / "normal-replay-metadata-witness.json", "load_queue_replay", path)
