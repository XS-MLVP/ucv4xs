"""Compose public transaction ledgers using OLD feedback at each shared edge.

Child reference reuse is not substitution of real DUT children. No internal
signal or register is sampled as an answer; a separate external UID actor
tracks dispatch, replay handshakes, bus/bypass consumption and completion.
"""
from dataclasses import asdict, replace
import json

from suites.memblock.lsq.native import ROOT
from suites.memblock.lsq.vlq.model import VirtualLoadQueueModel
from suites.memblock.lsq.vlq.types import Inputs as VlqInputs, QueuePtr, Writeback
from suites.memblock.lsq.rar.model import LoadQueueRarModel
from suites.memblock.lsq.rar.types import Inputs as RarInputs
from suites.memblock.lsq.raw.model import LoadQueueRawModel
from suites.memblock.lsq.raw.types import Inputs as RawInputs
from suites.memblock.lsq.replay.model import ReplayModel
from suites.memblock.lsq.replay.types import LqWakeup
from suites.memblock.lsq.load_uncache.model import LoadUncacheModel
from .codec import encode, replay_inputs


class LoadQueueModel:
    def __init__(self):
        specs = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]
        self.vlq = VirtualLoadQueueModel(specs["virtual_load_queue"])
        self.rar = LoadQueueRarModel(specs["load_queue_rar"])
        self.raw = LoadQueueRawModel(specs["load_queue_raw"], allow_head_recovery=True)
        self.replay, self.uncache = ReplayModel(), LoadUncacheModel()
        self.perf = self.perf_delay = None
        self.edges = 0

    def connected(self, inp):
        pins = encode(inp)
        vi = VlqInputs(inp.dispatch, tuple(Writeback(load.execution.valid, load.execution.uop.lq.value,
                                                   load.update_address, load.execution.need_replay) for load in inp.loads), inp.redirect, inp.reset)
        ri = RarInputs(inp.rar_queries, inp.rar_revoke_last, inp.rar_revoke_older, self.vlq.outputs.head, inp.redirect, inp.release, inp.reset)
        wi = RawInputs(inp.raw_queries, inp.stores, inp.raw_revoke_last, inp.raw_revoke_older, inp.address_ready, inp.redirect, inp.reset)
        uv = {key: value for key, value in pins.items() if key == "reset" or key.startswith(("io_redirect_", "io_rob_pendingPtr_", "io_uncache_", "io_bypass_"))}
        for lane, load in enumerate(inp.loads):
            prefix = f"io_ldu_ldin_{lane}_"
            uv.update({key.replace(prefix, f"io_req_{lane}_", 1): value for key, value in pins.items() if key.startswith(prefix)})
            uv[f"io_req_{lane}_valid"] = int(load.execution.valid and bool(load.execution.causes & 1))
        rar, raw, unc = self.rar.outputs_for(ri), self.raw.outputs_for(wi), self.uncache.expected(uv)
        wakes = {kind: LqWakeup(bool(unc[f"io_{kind}Wakeup_valid"]),
                               QueuePtr(bool(unc.get(f"io_{kind}Wakeup_bits_flag", 0)), unc.get(f"io_{kind}Wakeup_bits_value", 0))) for kind in ("mmio", "nc")}
        pi = replace(replay_inputs(inp), writeback=self.vlq.outputs.head, rar_full=rar.full, raw_full=raw.full, **wakes)
        return vi, ri, wi, pi, uv, rar, raw, unc

    def expected(self, inp):
        _, ri, wi, pi, uv, rar, raw, unc = self.connected(inp)
        v = self.vlq.outputs
        values = dict(io_lqEmpty=int(v.empty), io_lqDeq_valid=int(v.dequeue_valid),
                      io_lqRedirect_valid=int(v.recovery_valid), io_lqRecoverStall=int(v.recovery_stall))
        if v.dequeue_valid:
            values["io_lqDeq_bits"] = v.dequeue_count
        if v.recovery_valid:
            values.update(io_lqRedirect_bits_flag=int(v.recovery_ptr.flag), io_lqRedirect_bits_value=v.recovery_ptr.value)
        for lane in range(3):
            values[f"io_ldu_rarNukeQuery_{lane}_req_ready"] = int(rar.ready[lane])
            values[f"io_ldu_rawNukeQuery_{lane}_req_ready"] = int(raw.ready[lane])
            p = f"io_ldu_rarNukeQuery_{lane}_resp_"
            values[p + "valid"] = int(rar.responses[lane].valid)
            if rar.responses[lane].valid:
                values[p + "bits_nuke"] = int(rar.responses[lane].nuke)
        for lane, rb in enumerate(raw.rollbacks):
            p = f"io_nuke_rollback_{lane}_"
            values[p + "valid"] = int(rb.valid)
            if rb.valid:
                payload = dict(ftqIdx_flag=rb.ftq.flag, ftqIdx_value=rb.ftq.value, ftqOffset=rb.ftq_offset, isRVC=rb.is_rvc,
                               robIdx_flag=rb.rob.flag, robIdx_value=rb.rob.value, robIdx_isFormer=rb.rob.former,
                               stFtqIdx_flag=rb.store_ftq_flag, stFtqIdx_value=rb.store_ftq_value, stFtqOffset=rb.store_ftq_offset,
                               stIsRVC=rb.store_is_rvc, debug_runahead_checkpoint_id=rb.checkpoint)
                values.update({p + "bits_" + key: int(value) for key, value in payload.items()})
        train = raw.training
        values["io_mdpTrain_valid"] = int(train.valid)
        if train.valid:
            values.update({"io_mdpTrain_bits_" + key: int(value) for key, value in dict(ftqIdx_value=train.ftq_value, ftqOffset=train.ftq_offset,
                           isRVC=train.is_rvc, stFtqIdx_value=train.store_ftq_value, stFtqOffset=train.store_ftq_offset, stIsRVC=train.store_is_rvc).items()})
        # Allocated/selection/special state has asynchronous reset, unlike
        # the resetless histories above. It is already clear at pre-edge
        # when the reset pin rises, not only after advance(reset).
        replay_values = self.replay.expected(pi) if not inp.reset else {
            "io_replayAllocate": 0, "io_specialMode": 0,
            **{f"io_replay_{bank}_valid": 0 for bank in range(3)}}
        for key, value in replay_values.items():
            if key != "io_lqFull" and not key.startswith("io_perf_"):
                values[key] = value
        for key, value in unc.items():
            if key.startswith(("io_mmioWakeup_", "io_ncWakeup_")):
                continue
            values[key.replace("io_rollback_", "io_nack_rollback_0_", 1)] = value
        if self.perf is not None:
            values.update({f"io_perf_{lane}_value": int(count) for lane, count in enumerate(self.perf)})
        # These particular outputs are resetless history registers, NOT
        # reset state. Their value is unspecified before enough public idle
        # edges exist. Knownness advances only at session startup, never as
        # a way to mask an active-reset, response or functional mismatch.
        def known(name):
            edges = self.edges
            if name == "io_lqEmpty":
                return edges >= 1
            if name.startswith(("io_lqRedirect_", "io_lqRecoverStall")):
                return edges >= 3
            if name.startswith("io_lqDeq_"):
                return edges >= 2
            if "rarNukeQuery_" in name and "_resp_" in name:
                return edges >= 1
            if name.startswith("io_bypass_"):
                return edges >= (2 if "_s2Resp_" in name else 1)
            if name.startswith("io_exceptionInfo_"):
                return edges >= 1
            if name.startswith("io_perf_"):
                index = int(name.split("_")[2])
                return edges >= (4 if index < 17 else 5 if index == 25 else 3 if index == 26 else 2)
            return True
        return {key: value for key, value in values.items() if known(key)}

    def advance(self, inp):
        vi, ri, wi, pi, uv, rar, raw, unc = self.connected(inp)
        feedback = dict(ld_wb_ptr=asdict(self.vlq.outputs.head), rar_full=rar.full, raw_full=raw.full,
                        mmio=asdict(pi.mmio), nc=asdict(pi.nc))
        # Full predicates come from asynchronously reset FreeList occupancy
        # (FreeList.sv1217/2279, _1.sv728/1535, _2.sv1293/2782). Thus a
        # reset edge samples full_mask=0 into the resetless perf pipeline,
        # even when the previous non-reset edge had all three pools full.
        # This changes only the newly sampled event, NOT existing history,
        # startup knownness, the child's public-input ledger or output masks.
        mask = 0 if inp.reset else 4 * rar.full + 2 * raw.full + int(not self.replay.pool.available)
        old_perf = (rar.perf_fire, rar.perf_nuke, raw.perf_fire, raw.perf_rollback, *self.replay.perf,
                    *(int(mask == combination) for combination in range(8)), int(any(rb.valid for rb in raw.rollbacks)), int(unc["io_rollback_valid"]))
        assert len(old_perf) == 27
        # All connected inputs above are immutable OLD-state snapshots. Do not
        # reconnect after advancing one child: that would fabricate feedback.
        vc = self.vlq.advance(vi)
        rc = self.rar.advance(ri, rar.ready)
        wc = self.raw.advance(wi, raw.ready)
        replay_perf_history = self.replay.perf_delay
        pc = self.replay.advance(pi)
        if inp.reset:
            # Child perf is a resetless two-edge history even though the
            # allocated/selection state resets asynchronously. Preserve the
            # pending public event for its specified edge; never call it a
            # live Replay owner or restart startup masking on active reset.
            self.replay.perf, self.replay.perf_delay = replay_perf_history, (0,) * 13
        uc = self.uncache.advance(uv)
        self.perf, self.perf_delay = self.perf_delay, tuple(old_perf)
        self.edges += 1
        return dict(vlq=asdict(vc), rar=asdict(rc), raw=asdict(wc), replay=pc, uncache=uc, internal_feedback_before=feedback)
