from lsqverify.replay_cause_lifetimes import trace


async def test_same_original_UID_nine_real_replays_before_actual_LQ_release(lq, tmp_path):
    await trace(lq, tmp_path / "replay-cause-lifetime-witness.json", "load_queue")
