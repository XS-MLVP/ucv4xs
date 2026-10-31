"""Full real Wrapper checkpoint lifecycles; no synthetic child feedback."""

from dataclasses import replace
import hashlib
import json

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.replay.types import Cause
from suites.memblock.lsq.vlq.types import QueuePtr
from .memory_owners import MemoryOwners, cached_load
from .test_replay_population import drain_replays


class CheckpointMemoryOwners(MemoryOwners):
    def __init__(self, env):
        super().__init__(env)
        self.generation = 0
        self.public_slots = [{}, {}]
        self.payload_digest = hashlib.sha256()

    async def cycle(self, **fields):
        await super().cycle(**fields)
        ready = fields.get("replay_ready", self.base.replay_ready)
        before = self.env.pre_observed
        for bank in range(3):
            p = P.io(f"replay_{bank}_")
            if not before[p + "valid"] or not ready[bank]:
                continue
            slot = before[p + "bits_replayQueueIdx"]
            key = QueuePtr(bool(before[p + "bits_uop_lqIdx_flag"]), before[p + "bits_uop_lqIdx_value"])
            state = self.active_loads[key]
            checkpoint = state["load"].execution.uop.checkpoint
            assert before[p + "bits_uop_perfDebugInfo_runahead_checkpoint_id"] == checkpoint
            assert 0 <= slot < 120 and slot % 3 == bank
            assert slot not in self.public_slots[self.generation]
            self.public_slots[self.generation][slot] = state["uid"]
            self.payload_digest.update(json.dumps([self.generation, slot, state["uid"], checkpoint]).encode() + b"\n")


async def test_real_wrapper_checkpoint_high_low_pool_reuse(lsq, tmp_path):
    trace = CheckpointMemoryOwners(lsq)
    lifetimes = []
    for generation, checkpoint in enumerate(((1 << 64) - 1, 0)):
        trace.generation = generation
        loads = []
        for index in range(120):
            position = 120 * generation + index
            load = cached_load(position, 10 + position, 0, 0x100000 + 64 * position, 0x80100000 + 64 * position)
            req = load.execution
            loads.append(replace(load, execution=replace(req, uop=replace(req.uop, checkpoint=checkpoint),
                                 need_replay=True, causes=1 << Cause.BANK_CONFLICT)))
        await trace.dispatch(loads=loads)
        await trace.execute(loads)
        uids = {state["uid"] for state in trace.loads if state["load"] in loads}
        assert len(uids) == 120
        lsq.reach("LSQ-REPLAY.capacity", "LSQ-ALLOC.lq_capacity")
        await drain_replays(trace, uids)
        slots = trace.public_slots[generation]
        assert set(slots) == set(range(120)) and set(slots.values()) == uids
        assert all(state["completed"] for state in trace.loads if state["uid"] in uids)
        assert lsq.observed[P.p_lqEmpty] and lsq.observed[P.p_sqEmpty]
        assert not lsq.observed[P.p_replayAllocate]
        lsq.prove("LSQ-REPLAY.capacity", "LSQ-ALLOC.lq_capacity")
        lifetimes.append(dict(generation=generation, checkpoint=checkpoint, public_slots=sorted(slots),
                              replay_handshakes=120, feedback_and_ordered_completions=120,
                              uid_first=min(uids), uid_last=max(uids)))
    assert trace.load_released == 240 and len(trace.loads) == 240
    witness = dict(format="lsq-wrapper-checkpoint-pool-witness-v1", lifetimes=lifetimes,
                   completed_uids=240, payload_stream_SHA256=trace.payload_digest.hexdigest(),
                   scope="Full real LsqWrapper hierarchy; load-only capacity workload, public Replay grants/S3 feedback/LQ credits; no mixed Store acceptance claim.")
    (tmp_path / "checkpoint-pool-witness.json").write_text(json.dumps(witness, indent=2) + "\n")
