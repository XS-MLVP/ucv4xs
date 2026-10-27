"""Small calibration only; never a substitute for the full public-slot loops."""
import pytest

from lsqverify.normal_replay_metadata import PATHS, trace
from tests.lsq_wrapper.conftest import lsq
from tests.load_queue.conftest import lq


@pytest.mark.parametrize("path", PATHS)
async def test_normal_metadata_leaf_probe(replay, tmp_path, path):
    await trace(replay, tmp_path / "normal-replay-metadata-witness.json", "load_queue_replay", path, per_profile=2)


@pytest.mark.parametrize("path", PATHS)
async def test_normal_metadata_LQ_probe(lq, tmp_path, path):
    await trace(lq, tmp_path / "normal-replay-metadata-witness.json", "load_queue", path, per_profile=2)


@pytest.mark.parametrize("path", PATHS)
async def test_normal_metadata_Wrapper_probe(lsq, tmp_path, path):
    await trace(lsq, tmp_path / "normal-replay-metadata-witness.json", "lsq_wrapper", path, per_profile=2)
