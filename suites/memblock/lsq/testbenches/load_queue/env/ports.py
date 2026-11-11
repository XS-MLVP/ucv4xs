"""Passive full pin sample, with an independently written transaction decoder."""
import json

from suites.memblock.lsq.testbenches.shared.env.dut import ROOT
from suites.memblock.lsq.testbenches.raw.transactions import FtqPtr
from suites.memblock.lsq.testbenches.raw.transactions import Query as RawQuery
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.raw.transactions import Store
from suites.memblock.lsq.testbenches.rar.transactions import Query as RarQuery
from suites.memblock.lsq.testbenches.rar.transactions import Release
from suites.memblock.lsq.testbenches.replay.env.ports import decode as replay_decode
from suites.memblock.lsq.testbenches.replay.env.codec import encode as replay_encode
from suites.memblock.lsq.testbenches.replay.transactions import Inputs as ReplayInputs
from suites.memblock.lsq.testbenches.vlq.transactions import Dispatch
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr
from suites.memblock.lsq.testbenches.vlq.transactions import Redirect
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.load_queue.env.codec import encode
from suites.memblock.lsq.testbenches.load_queue.env.codec import ports
from suites.memblock.lsq.testbenches.load_queue.transactions import Bus
from suites.memblock.lsq.testbenches.load_queue.transactions import Bypass
from suites.memblock.lsq.testbenches.load_queue.transactions import EXCEPTION_BITS
from suites.memblock.lsq.testbenches.load_queue.transactions import Inputs
from suites.memblock.lsq.testbenches.load_queue.transactions import Load
from suites.memblock.lsq.testbenches.load_queue.transactions import BypassResponse
from suites.memblock.lsq.testbenches.load_queue.transactions import NukeQuery
from suites.memblock.lsq.testbenches.load_queue.transactions import NukeRollback
from suites.memblock.lsq.testbenches.load_queue.transactions import Observation
from suites.memblock.lsq.testbenches.load_queue.transactions import ReplaySlot


def decode(pins):
    def rob(prefix):
        return RobPtr(bool(pins[prefix + "flag"]), pins[prefix + "value"], bool(pins[prefix + "isFormer"]))
    def lq(prefix):
        return QueuePtr(bool(pins[prefix + "flag"]), pins[prefix + "value"])
    def sq(prefix):
        return SqPtr(bool(pins[prefix + "first_flag"]), bool(pins[prefix + "second_flag"]), pins[prefix + "value"])
    # Reconstruct only the retained Replay subset; internal placeholders below
    # are decoder defaults and are never driveable through the LoadQueue type.
    child = replay_encode(ReplayInputs())
    for name in child:
        source = name
        if name.startswith("io_enq_"):
            source = name.replace("io_enq_", "io_ldu_ldin_", 1)
        elif name.startswith(("io_stAddrReady", "io_stDataReady", "io_sqDeqPtr_", "io_physicalUpperSqIdx_")):
            source = name.replace("io_", "io_sq_", 1)
        elif name == "io_sqEmpty":
            source = "io_sq_sqEmpty"
        elif name.startswith("io_robHeadPtr_"):
            source = name.replace("io_robHeadPtr_", "io_rob_pendingPtrNext_", 1)
        elif name.startswith("io_storeDataWrite_"):
            source = name.replace("io_storeDataWrite_", "io_std_storeDataIn_", 1).replace("_bits_", "_bits_sqIdx_", 1)
        elif name.startswith(("io_storeAddrWakeup_", "io_storeDataWakeup_")):
            kind, lane, suffix = name.removeprefix("io_").split("_", 2)
            source = f"io_wakeupToLRQ_{int(lane) + (2 if kind == 'storeDataWakeup' else 0)}_{suffix}"
        if source in pins:
            child[name] = pins[source]
    rp = replay_decode(child)
    loads, rar, raw, stores, dispatch, bypass = [], [], [], [], [], []
    for lane in range(3):
        p = f"io_ldu_ldin_{lane}_bits_"
        loads.append(Load(rp.enqueues[lane], pins[p + "fullva"], pins[p + "paddr"], pins[p + "gpaddr"], bool(pins[p + "mmio"]),
                          bool(pins[p + "memBackTypeMM"]), bool(pins[p + "isHyper"]), bool(pins[p + "isForVSnonLeafPTE"]),
                          bool(pins[p + "updateAddrValid"]), sum(pins[p + f"uop_exceptionVec_{bit}"] << bit for bit in EXCEPTION_BITS)))
        p = f"io_ldu_rarNukeQuery_{lane}_req_"
        rar.append(RarQuery(bool(pins[p + "valid"]), rob(p + "bits_robIdx_"), lq(p + "bits_lqIdx_"), pins[p + "bits_paddr"], bool(pins[p + "bits_dataValid"]), bool(pins[p + "bits_nc"])))
        p = f"io_ldu_rawNukeQuery_{lane}_req_"
        raw.append(RawQuery(bool(pins[p + "valid"]), rob(p + "bits_robIdx_"), sq(p + "bits_sqIdx_"), pins[p + "bits_paddr"], pins[p + "bits_mask"],
                            bool(pins[p + "bits_dataValid"]), bool(pins[p + "bits_isRVC"]), FtqPtr(bool(pins[p + "bits_ftqPtr_flag"]), pins[p + "bits_ftqPtr_value"]),
                            pins[p + "bits_ftqOffset"], pins[p + "bits_debugInfo_runahead_checkpoint_id"]))
        p = f"io_bypass_{lane}_s0Req_"
        bypass.append(Bypass(bool(pins[p + "valid"]), lq(p + "bits_lqIdx_"), bool(pins[p + "bits_isNCReplay"]), bool(pins[p + "bits_isMMIOReplay"])))
    for lane in range(8):
        p = f"io_enq_req_{lane}_"
        dispatch.append(Dispatch(bool(pins[p + "valid"]), rob(p + "bits_robIdx_"), lq(p + "bits_lqIdx_"), pins[p + "bits_numLsElem"]))
    for lane in range(2):
        p = f"io_sta_storeAddrIn_{lane}_"
        stores.append(Store(bool(pins[p + "valid"]), rob(p + "bits_uop_robIdx_"), pins[p + "bits_paddr"], pins[p + "bits_mask"], bool(pins[p + "bits_wlineflag"]),
                            bool(pins[p + "bits_tlbMiss"]), bool(pins[p + "bits_uop_ftqPtr_flag"]), pins[p + "bits_uop_ftqPtr_value"], pins[p + "bits_uop_ftqOffset"], bool(pins[p + "bits_uop_isRVC"])))
    p = "io_uncache_"
    bus = Bus(bool(pins[p + "req_ready"]), bool(pins[p + "idResp_valid"]), pins[p + "idResp_bits_mid"], pins[p + "idResp_bits_sid"],
              bool(pins[p + "resp_valid"]), pins[p + "resp_bits_id"], pins[p + "resp_bits_data"], bool(pins[p + "resp_bits_error"]), bool(pins[p + "resp_bits_nderr"]))
    return Inputs(dispatch=tuple(dispatch), loads=tuple(loads), rar_queries=tuple(rar), raw_queries=tuple(raw), stores=tuple(stores),
                  **{f"{family}_revoke_{age}": tuple(bool(pins[f"io_ldu_{family}NukeQuery_{lane}_" + suffix]) for lane in range(3))
                     for family in ("rar", "raw") for age, suffix in (("last", "revokeLastCycle"), ("older", "revokeLastLastCycle"))},
                  replay_ready=rp.ready, address_wakeups=rp.address_wakeups, data_wakeups=rp.data_wakeups, data_writes=rp.data_writes,
                  refills=rp.refills, l2_hints=rp.l2_hints, slow_tlb=rp.slow_tlb, fast_tlb=rp.fast_tlb, address_ready=rp.address_ready,
                  address_bits=rp.address_bits, data_ready=rp.data_ready, data_bits=rp.data_bits, dequeue=rp.dequeue, upper=rp.upper,
                  sq_empty=rp.sq_empty, pending=rob("io_rob_pendingPtr_"), pending_next=rp.head,
                  release=Release(bool(pins["io_release_valid"]), pins["io_release_bits_paddr"]), bypass=tuple(bypass), bus=bus,
                  redirect=Redirect(bool(pins["io_redirect_valid"]), rob("io_redirect_bits_robIdx_"), bool(pins["io_redirect_bits_level"])), reset=bool(pins["reset"]))


class Ports:
    def __init__(self, dut):
        self.dut, self.inputs, self.outputs = dut, {}, {}
        def walk(node, prefix=()):
            if "Pin" in node:
                name = "_".join(prefix)
                if name != "clock":
                    (self.inputs if node["Pin"] == "input" else self.outputs)[name] = getattr(dut, name)
            else:
                for name, child in node.items():
                    if isinstance(child, dict):
                        walk(child, (*prefix, name))
        walk(json.loads((ROOT / "dut/load_queue/signals.json").read_text()))
        assert set(self.inputs) == set(encode(Inputs())) == set(ports()["input"]) and set(self.outputs) == set(ports()["output"])

    def sample(self, event):
        actual = {name: pin.U() for name, pin in self.inputs.items()}
        return decode(actual), {name: pin.U() for name, pin in self.outputs.items()}, actual

    def observe(self, pins):
        """Decode one sampled public window into immutable LoadQueue responses."""
        def rollback(prefix):
            return NukeRollback(bool(pins[prefix + "valid"]), pins.get(prefix + "bits_robIdx_value", 0),
                                pins.get(prefix + "bits_stFtqIdx_value", 0),
                                pins.get(prefix + "bits_debug_runahead_checkpoint_id", 0))

        replays = tuple(ReplaySlot(
            bool(pins[f"io_replay_{bank}_valid"]), pins[f"io_replay_{bank}_bits_replayQueueIdx"],
            bool(pins[f"io_replay_{bank}_bits_uop_lqIdx_flag"]), pins[f"io_replay_{bank}_bits_uop_lqIdx_value"],
            pins[f"io_replay_{bank}_bits_uop_perfDebugInfo_runahead_checkpoint_id"]) for bank in range(3))
        bypass = tuple(BypassResponse(
            bool(pins[f"io_bypass_{lane}_s1Resp_valid"]), bool(pins[f"io_bypass_{lane}_s2Resp_valid"]),
            pins[f"io_bypass_{lane}_s1Resp_bits_paddr"], pins[f"io_bypass_{lane}_s2Resp_bits_data"], bool(pins[f"io_bypass_{lane}_s2Resp_bits_derr"]),
            bool(pins[f"io_bypass_{lane}_s2Resp_bits_nderr"])) for lane in range(3))
        rar = tuple(NukeQuery(bool(pins[f"io_ldu_rarNukeQuery_{lane}_req_ready"]), bool(pins[f"io_ldu_rarNukeQuery_{lane}_resp_valid"]),
                              bool(pins[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"])) for lane in range(3))
        raw = tuple(NukeQuery(bool(pins[f"io_ldu_rawNukeQuery_{lane}_req_ready"])) for lane in range(3))
        return Observation(
            bool(pins["io_lqEmpty"]), bool(pins["io_mdpTrain_valid"]), bool(pins["io_replayAllocate"]),
            bool(pins["io_specialMode"]), bool(pins["io_exceptionInfo_valid"]), pins["io_exceptionInfo_bits_vaddr"],
            bool(pins["io_uncache_req_valid"]), pins["io_uncache_req_bits_addr"], pins["io_uncache_req_bits_id"],
            bool(pins["io_uncache_req_bits_nc"]), rollback("io_nack_rollback_0_"),
            (rollback("io_nuke_rollback_0_"), rollback("io_nuke_rollback_1_")), replays, bypass, rar, raw)
