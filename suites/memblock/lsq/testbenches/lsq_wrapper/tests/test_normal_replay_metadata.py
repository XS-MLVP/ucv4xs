import pytest

from suites.memblock.lsq.testbenches.replay.model.normal_replay_metadata import PATHS
from suites.memblock.lsq.testbenches.replay.model.normal_replay_metadata import trace


@pytest.mark.parametrize("path", PATHS)
async def test_normal_scalar_original_UID_real_Forward_Replay_pipeline_and_release(lsq, tmp_path, path):
    await trace(lsq, tmp_path / "normal-replay-metadata-witness.json", "lsq_wrapper", path)
