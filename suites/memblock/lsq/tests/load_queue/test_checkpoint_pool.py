"""Real five-child parent proof from contracts/replay-checkpoint-pool.md."""
from dataclasses import replace
import hashlib
import json

from lsqverify.load_queue.actor import LoadActor
from lsqverify.load_queue.types import Inputs
from lsqverify.replay.types import Cause
from lsqverify.vlq.types import QueuePtr


class CheckpointActor(LoadActor):
    """Add a compact public-output witness without using reference state."""
    def __init__(self, env):
        super().__init__(env)
        self.generation = 0
        self.public_slots = [{}, {}]
        self.payload_digest = hashlib.sha256()

    async def step(self, inp=None, *, new_owners=()):
        inp = inp or Inputs()
        result = await super().step(inp, new_owners=new_owners)
        before = self.env.pre_observed
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if not before[p + "valid"] or not inp.replay_ready[bank]:
                continue
            slot = before[p + "bits_replayQueueIdx"]
            lq = QueuePtr(bool(before[p + "bits_uop_lqIdx_flag"]), before[p + "bits_uop_lqIdx_value"])
            owner = next(o for o in self.all.values() if QueuePtr.encode(o.position) == lq)
            checkpoint = owner.load.execution.uop.checkpoint
            assert before[p + "bits_uop_perfDebugInfo_runahead_checkpoint_id"] == checkpoint
            assert slot not in self.public_slots[self.generation]
            self.public_slots[self.generation][slot] = owner.uid
            self.payload_digest.update(json.dumps([self.generation, slot, owner.uid, checkpoint]).encode() + b"\n")
        return result


async def test_real_parent_checkpoint_high_low_pool_reuse(lq, tmp_path):
    actor = CheckpointActor(lq)
    lifetimes = []
    for generation, checkpoint in enumerate(((1 << 64) - 1, 0)):
        actor.generation = generation

        def configure(load):
            req = load.execution
            return replace(load, execution=replace(req, uop=replace(req.uop, checkpoint=checkpoint),
                           need_replay=True, causes=1 << Cause.BANK_CONFLICT))

        uids = []
        for _ in range(15):
            uids.extend(await actor.dispatch((1,) * 8, configure=configure))
        assert len(uids) == 120 and actor.tail - actor.head == 120
        for offset in range(0, 120, 3):
            await actor.execute(uids[offset:offset + 3], lanes=(0, 1, 2))
        lq.reach("LQ-REPLAY.checkpoint_pool", "LQ-REPLAY.metadata", "LQ-CAPACITY.replay_pool")
        # The actor returns exactly the observed public slot to shared S3 and
        # waits for the real VLQ's ordered release, not a local model-empty bit.
        await actor.drain()
        slots = actor.public_slots[generation]
        assert set(slots) == set(range(120)) and set(slots.values()) == set(uids)
        assert set(uids) <= actor.completed and not actor.live and not actor.issued
        assert {actor.owner(uid).feedback_slot for uid in uids} == set(range(120))
        actor.checked(("LQ-REPLAY.checkpoint_pool", "LQ-REPLAY.metadata", "LQ-CAPACITY.replay_pool"), uids)
        lifetimes.append(dict(generation=generation, checkpoint=checkpoint,
                              public_slots=sorted(slots), replay_handshakes=120,
                              feedback_and_ordered_completions=120,
                              uid_first=min(uids), uid_last=max(uids)))
    assert len(actor.completed) == 240
    witness = dict(format="lsq-parent-checkpoint-pool-witness-v1", lifetimes=lifetimes,
                   completed_uids=240, payload_stream_SHA256=actor.payload_digest.hexdigest(),
                   scope="Real LoadQueue children, external actor, public replayQueueIdx, shared S3 feedback and VLQ ordered completion.")
    (tmp_path / "checkpoint-pool-witness.json").write_text(json.dumps(witness, indent=2) + "\n")
