import pytest

from lsqverify.normal_replay_metadata import PATHS, trace


@pytest.mark.parametrize("path", PATHS)
async def test_normal_scalar_original_UID_pipeline_dependency_and_actual_LQ_release(lq, tmp_path, path):
    await trace(lq, tmp_path / "normal-replay-metadata-witness.json", "load_queue", path)
