from lsqverify.replay_cause_lifetimes import trace
from tests.load_queue.conftest import lq
from tests.lsq_wrapper.conftest import lsq


async def test_original_cause_lifetime_leaf_probe(replay, tmp_path):
    await trace(replay, tmp_path / "replay-cause-lifetime-witness.json", "load_queue_replay", count=8)


async def test_original_cause_lifetime_LQ_probe(lq, tmp_path):
    await trace(lq, tmp_path / "replay-cause-lifetime-witness.json", "load_queue", count=8)


async def test_original_cause_lifetime_Wrapper_probe(lsq, tmp_path):
    await trace(lsq, tmp_path / "replay-cause-lifetime-witness.json", "lsq_wrapper", count=8)
