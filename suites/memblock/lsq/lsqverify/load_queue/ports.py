"""Passive full pin sample, with an independently written transaction decoder."""
import json

from lsqverify.native import ROOT
from lsqverify.raw.types import FtqPtr, Query as RawQuery, SqPtr, Store
from lsqverify.rar.types import Query as RarQuery, Release
from lsqverify.replay.ports import decode as replay_decode
from lsqverify.replay.codec import encode as replay_encode
from lsqverify.replay.types import Inputs as ReplayInputs
from lsqverify.vlq.types import Dispatch, QueuePtr, Redirect, RobPtr
from .codec import encode, ports
from .types import Bus, Bypass, EXCEPTION_BITS, Inputs, Load


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
