"""Full passive sample; wrapper decoder is separate from its encode mapping."""
from dataclasses import asdict
import json

from lsqverify.native import ROOT
from lsqverify.forward.types import Query, Translation
from lsqverify.load_queue.codec import encode as load_encode
from lsqverify.load_queue.ports import decode as load_decode
from lsqverify.load_queue.types import Inputs as LoadInputs
from lsqverify.psq.types import Attributes, SecondPage
from lsqverify.raw.types import FtqPtr, SqPtr
from lsqverify.vlq.types import QueuePtr, RobPtr
from .codec import encode, ports
from .types import Address, Bus, Data, Dispatch, Inputs


def decode(pins):
    def pointer(prefix, kind):
        if kind == "rob":
            return RobPtr(bool(pins[prefix + "flag"]), pins[prefix + "value"], bool(pins[prefix + "isFormer"]))
        if kind == "lq":
            return QueuePtr(bool(pins[prefix + "flag"]), pins[prefix + "value"])
        return SqPtr(bool(pins[prefix + "first_flag"]), bool(pins[prefix + "second_flag"]), pins[prefix + "value"])
    # Only an adapter shape, not inferred internal SQ values. Child-only
    # feedback placeholders are discarded: wrapper Inputs cannot expose them.
    child = load_encode(LoadInputs())
    for name in child:
        if name.startswith(("io_enq_", "io_sq_")):
            continue
        source = "io_brqRedirect_" + name[len("io_redirect_"):] if name.startswith("io_redirect_") else name
        child[name] = pins[source]
    load = load_decode(child)
    names = ("loads", "rar_queries", "raw_queries", "rar_revoke_last", "rar_revoke_older", "raw_revoke_last", "raw_revoke_older",
             "replay_ready", "address_wakeups", "data_wakeups", "refills", "l2_hints", "slow_tlb", "fast_tlb", "pending", "pending_next",
             "release", "bypass", "redirect", "reset")
    values = {name: getattr(load, name) for name in names}
    dispatch = []
    for lane in range(8):
        prefix = f"io_enq_req_{lane}_"
        dispatch.append(Dispatch(bool(pins[prefix + "valid"]), pins[f"io_enq_needAlloc_{lane}"],
                                 pointer(prefix + "bits_uop_robIdx_", "rob"), pins[prefix + "bits_uop_numLsElem"],
                                 pointer(prefix + "bits_reqStartPtr_lqIdx_", "lq"), pointer(prefix + "bits_reqEndPtr_sqIdx_", "sq")))
    addresses, attributes, data, pages = [], [], [], []
    for lane in range(2):
        p, raw = f"io_sta_storeAddrIn_{lane}_", load.stores[lane]
        addresses.append(Address(valid=bool(pins[p + "valid"]), slot=pins[p + "bits_uop_sqIdx_value"],
                                 fu_op=pins[p + "bits_uop_fuOpType"], vaddr=pins[p + "bits_vaddr"], paddr=pins[p + "bits_paddr"],
                                 size=pins[p + "bits_size"], tlb_miss=bool(pins[p + "bits_tlbMiss"]), hyper=bool(pins[p + "bits_isHyper"]),
                                 unaligned=bool(pins[p + "bits_isUnalign"]), cross_word=bool(pins[p + "bits_cross16Byte"]),
                                 last=bool(pins[p + "bits_isLastRequest"]), rob=raw.rob, ftq=FtqPtr(raw.ftq_flag, raw.ftq_value),
                                 ftq_offset=raw.ftq_offset, rvc=raw.is_rvc, mask=raw.mask, wline=raw.wline))
        p = f"io_sta_storeAddrInRe_{lane}_"
        attributes.append(Attributes(**{field: bool(pins[p + suffix]) for field, suffix in
                                       (("nc", "nc"), ("mmio", "mmio"), ("memory", "memBackTypeMM"),
                                        ("exception", "hasException"), ("last", "isLastRequest"))}))
        p = f"io_std_storeDataIn_{lane}_"
        data.append(Data(bool(pins[p + "valid"]), pointer(p + "bits_sqIdx_", "sq"), pins[p + "bits_fuOpType"], pins[p + "bits_data"]))
        p = f"io_sta_unalignQueueReq_{lane}_"
        pages.append(SecondPage(bool(pins[p + "valid"]), pointer(p + "bits_sqIdx_", "sq"), pins[p + "bits_paddr"]))
    queries, translations = [], []
    for lane in range(3):
        p = f"io_forward_{lane}_"
        queries.append(Query(bool(pins[p + "s0Req_valid"]), pins[p + "s0Req_bits_vaddr"], pointer(p + "s0Req_bits_sqIdx_", "sq"),
                             pins[p + "s0Req_bits_size"], bool(pins[p + "s0Req_bits_loadWaitBit"]),
                             bool(pins[p + "s0Req_bits_loadWaitStrict"]), pointer(p + "s0Req_bits_waitSqIdx_", "sq")))
        translations.append(Translation(pins[p + "s1Req_paddr"], bool(pins[p + "s1Kill"])))
    return Inputs(**values, dispatch=tuple(dispatch), addresses=tuple(addresses), attributes=tuple(attributes), data=tuple(data),
                  second_pages=tuple(pages), queries=tuple(queries), translations=tuple(translations),
                  bus=Bus(**asdict(load.bus), ack_to_load=bool(pins["io_uncache_idResp_bits_is2lq"]),
                          response_to_load=bool(pins["io_uncache_resp_bits_is2lq"]), outstanding=bool(pins["io_uncacheOutstanding"])),
                  sbuffer_ready=tuple(bool(pins[f"io_sbuffer_req_{lane}_ready"]) for lane in range(2)),
                  **{name: bool(pins[pin]) for name, pin in (("sbuffer_empty", "io_flushSbuffer_empty"), ("cache_ready", "io_cmoOpReq_ready"),
                     ("cache_response", "io_cmoOpResp_valid"), ("cache_denied", "io_cmoOpResp_bits_denied"),
                     ("cache_corrupt", "io_cmoOpResp_bits_corrupt"), ("writeback_ready", "io_mmioStout_ready"))})


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
        walk(json.loads((ROOT / "dut/lsq_wrapper/signals.json").read_text()))
        assert set(self.inputs) == set(ports()["input"]) == set(encode(Inputs()))
        assert set(self.outputs) == set(ports()["output"])

    def sample(self, event):
        actual = {name: signal.U() for name, signal in self.inputs.items()}
        return decode(actual), {name: signal.U() for name, signal in self.outputs.items()}, actual
