"""Pinned OPEN LDU S0/S1/S2/S3 boundary, original UID recovery and effects.

Deliberately small aligned-cached producer; not the full-domain random actor.
No DUT/model private state, expected/change dictionaries or known-issue reads.
"""
from dataclasses import replace

from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.forward.transactions import Translation
from suites.memblock.lsq.testbenches.load_queue.transactions import Load
from suites.memblock.lsq.testbenches.rar.transactions import Query as RarQuery
from suites.memblock.lsq.testbenches.rar.transactions import Release
from suites.memblock.lsq.testbenches.raw.transactions import Query as RawQuery
from suites.memblock.lsq.testbenches.replay.transactions import Cause
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import rob_number
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.recovery_owners import RecoveryOwners
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.public import obs, lane_forward, all_nuke, lane_replay


class LduRarOwners(RecoveryOwners):
    async def pipeline(self, load, lane, *, cause=None, expected_nuke=False,
                       release_window="none", s2_fields=None, feedback=False):
        q, u = load.execution, load.execution.uop
        assert lane in range(3) and not load.mmio and not q.nc
        assert not q.vaddr % 8 and not load.paddr % 8 and q.mask == 255
        assert cause in (None, Cause.CACHE_REPLAY, Cause.VIOLATION)
        state = self.active_loads[u.lq]
        assert not state["sent"] and not state["cancelled"]
        assert not feedback or "grant" in state
        release = Release(True, load.paddr)
        queries, translations = [Query()]*3, [Translation()]*3
        queries[lane] = Query(True, q.vaddr, u.sq, (u.operation >> 1) & 7,
                              u.load_wait, u.strict, u.wait_sq)
        await self.cycle(queries=tuple(queries))  # S0
        translations[lane] = Translation(load.paddr)
        await self.cycle(translations=tuple(translations),
                         release=release if release_window == "previous" else Release())  # S1
        self.env.expect(obs(forward=lane_forward(lane, valid=1)), "original S0 query reached S2 after its S1 PA")
        rar, raw = [RarQuery()]*3, [RawQuery()]*3
        # DCache hit, or MSHR-nack with miss=bankConflict=0: dataValid=1.
        rar[lane] = RarQuery(True, u.rob, u.lq, load.paddr, True, False)
        raw[lane] = RawQuery(True, u.rob, u.sq, load.paddr, q.mask, True,
                             u.rvc, u.ftq, u.offset, u.checkpoint)
        fields = dict(rar_queries=tuple(rar), raw_queries=tuple(raw),
                      release=release if release_window == "current" else Release())
        fields.update(s2_fields or {})
        if cause == Cause.VIOLATION:
            matches = [a for a in fields.get("addresses", ()) if a.valid and not a.tlb_miss
                       and rob_number(a.rob) < rob_number(u.rob)
                       and a.paddr//16 == load.paddr//16 and a.mask & q.mask]
            assert len(matches) == 1, "C_NK requires original concurrent older STA, not RAR nuke"
        await self.cycle(**fields)  # S2
        self.env.expect(obs(rar_nuke=all_nuke((lane,), req_ready=1), raw_nuke=all_nuke((lane,), req_ready=1)),
            "small original queries accepted", before=True)
        self.env.expect(obs(rar_nuke=all_nuke((lane,), resp_valid=1, nuke=int(expected_nuke))),
                        "RAR nuke is original reader ordering, not an LRQ cause")
        query_tick = self.env.last_tick
        execution = replace(q, need_replay=cause is not None, causes=0 if cause is None else 1 << cause,
                            replay_feedback=feedback, slot=state.get("grant", 0) if feedback else 0)
        packets = [Load()]*3
        packets[lane] = replace(load, execution=execution)
        revoke = tuple(n == lane and cause is not None for n in range(3))
        await self.cycle(loads=tuple(packets), rar_revoke_last=revoke, raw_revoke_last=revoke)  # S3
        assert self.env.last_tick == query_tick+2
        self.env.emit("ldu_original_S2_S3", uid=state["uid"], query_tick=query_tick, lane=lane,
                      RAR_nuke=bool(expected_nuke), S3_cause=None if cause is None else int(cause),
                      revoke_same_lane=cause is not None, replay_feedback=feedback,
                      original_slot=execution.slot if feedback else None,
                      route="original_ROB_flushAfter" if expected_nuke else "no_RAR_rollback")
        return bool(expected_nuke)

    async def grant(self, load):
        u = load.execution.uop
        for _ in range(80):
            banks = [b for b, replay in enumerate(self.env.response.replays) if replay.valid
                     and replay.lq_idx_flag == int(u.lq.flag) and replay.lq_idx_value == u.lq.value]
            if banks:
                break
            await self.cycle()
        assert len(banks) == 1, "original replay must actually be offered"
        b = banks[0]
        self.env.expect(obs(replays=lane_replay(b, rob_idx_flag=int(u.rob.flag), rob_idx_value=u.rob.value,
            rob_idx_former=int(u.rob.former))), "Replay grant original ROB identity")
        await self.cycle(replay_ready=tuple(n == b for n in range(3)))
        self.env.emit("ldu_original_replay_grant", uid=self.active_loads[u.lq]["uid"],
                      bank=b, slot=self.active_loads[u.lq]["grant"])

    async def finish(self, **fields):
        assert all(s["cancelled"] or s["sent"] for s in self.loads), "no helper-only S3 completion"
        await super().finish(**fields)
