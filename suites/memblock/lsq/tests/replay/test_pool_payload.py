"""Full-pool public-output proof, defined in replay-checkpoint-pool.md."""
from dataclasses import replace
import hashlib
import json

from lsqverify.replay.types import Cause
from lsqverify.vlq.types import QueuePtr


async def test_checkpoint_high_low_lifetimes_at_every_public_replay_slot(replay, tmp_path):
    env = replay
    lifetimes = []
    stream = hashlib.sha256()
    all_uids = []
    for generation, checkpoint in enumerate(((1 << 64) - 1, 0)):
        await env.cycle(ready=(False,) * 3, writeback=QueuePtr.encode(120 * generation))
        requests = {}
        uids = []
        for offset in range(0, 120, 3):
            group = {}
            for lane in range(3):
                index = offset + lane
                req = env.request(
                    Cause.BANK_CONFLICT, rob=20 + 160 * generation + index,
                    lq=120 * generation + index, tag=index + 1,
                    vaddr=((1 << 50) - 1920 if not generation else 0x10000) + 16 * index,
                )
                req = replace(req, uop=replace(req.uop, checkpoint=checkpoint, operation=6))
                requests[(int(req.uop.lq.flag), req.uop.lq.value)] = req
                group[(lane + generation) % 3] = req
            change = await env.cycle(group)
            assert len(change["allocated"]) == 3
            uids.extend(owner["uid"] for owner in change["allocated"])
        assert env.observed["io_lqFull"] and env.observed["io_replayAllocate"]
        env.arm("LRQ-PAYLOAD.pool_checkpoint", uids)

        # Only public replay outputs choose which request is fed back. The
        # independent model remains active but is not the source of slot IDs.
        issued = {}
        issued_lq = set()
        for _ in range(240):
            beats = []
            for bank in range(3):
                p = f"io_replay_{bank}_"
                if not env.observed[p + "valid"]:
                    continue
                slot = env.observed[p + "bits_replayQueueIdx"]
                identity = (env.observed[p + "bits_uop_lqIdx_flag"], env.observed[p + "bits_uop_lqIdx_value"])
                assert 0 <= slot < 120 and slot % 3 == bank and slot not in issued
                assert identity in requests and identity not in issued_lq
                req = requests[identity]
                assert env.observed[p + "bits_uop_perfDebugInfo_runahead_checkpoint_id"] == checkpoint
                assert env.observed[p + "bits_vaddr"] == req.vaddr
                beats.append((slot, identity, req))
                stream.update(json.dumps([generation, slot, identity, checkpoint, req.vaddr]).encode() + b"\n")
            change = await env.cycle(ready=(True,) * 3)
            assert len(change["fired"]) == len(beats)
            for slot, identity, req in beats:
                issued[slot] = req
                issued_lq.add(identity)
            if len(issued) == 120:
                break
        else:
            raise AssertionError("not every public replay slot actually handshook")
        assert set(issued) == set(range(120)) and len(issued_lq) == 120
        # Every request has issued, but none has yet returned a completion.
        assert env.observed["io_lqFull"] and env.observed["io_replayAllocate"]
        env.arm(("LRQ-BANK.all_slots", "LRQ-RECYCLE.public_slots"), uids)
        for offset in range(0, 120, 3):
            feedback = {
                (lane + generation + 1) % 3: replace(
                    issued[offset + lane], replay_feedback=True, slot=offset + lane, need_replay=False,
                )
                for lane in range(3)
            }
            change = await env.cycle(feedback, ready=(False,) * 3)
            assert len(change["completed"]) == 3
        await env.idle(50, ready=(False,) * 3)
        assert set(uids) <= env.coverage.completed
        assert not env.observed["io_replayAllocate"] and not env.observed["io_lqFull"]
        all_uids.extend(uids)
        lifetimes.append(dict(generation=generation, checkpoint=checkpoint, allocated=120,
                              public_slots=sorted(issued), handshakes=120, feedback_completed=120))
    assert len(set(all_uids)) == 240
    witness = dict(format="lsq-replay-checkpoint-pool-witness-v1", lifetimes=lifetimes,
                   distinct_uids=240, payload_stream_SHA256=stream.hexdigest(),
                   scope="Public replayQueueIdx/valid/ready payload and feedback; independent model active on every edge.")
    (tmp_path / "checkpoint-pool-witness.json").write_text(json.dumps(witness, indent=2) + "\n")
