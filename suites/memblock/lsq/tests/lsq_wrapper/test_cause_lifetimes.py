from lsqverify.replay_cause_lifetimes import trace


async def test_same_original_UID_nine_Forward_S3_replays_then_real_release(lsq, tmp_path):
    await trace(lsq, tmp_path / "replay-cause-lifetime-witness.json", "lsq_wrapper")
