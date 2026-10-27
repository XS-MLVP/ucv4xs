from lsqverify.replay_cause_lifetimes import trace


async def test_same_original_UID_nine_grants_change_cause_at_every_public_slot(replay, tmp_path):
    await trace(replay, tmp_path / "replay-cause-lifetime-witness.json", "load_queue_replay")
