"""Public-history composition over both REAL native child hierarchies.

No DUT internal reads. OLD SQ readiness and both OLD request candidates are
captured before either child advances. Shared bus ownership is a transaction
ledger, not an unqualified response pulse clearing a copied RTL state enum.
All 39 retained perf outputs have explicit history models. Store events travel
through three real two-register boundaries, independently of Load perf.
"""
from dataclasses import asdict, replace

from suites.memblock.lsq.load_queue.model import LoadQueueModel
from suites.memblock.lsq.store_queue.model import StoreQueueModel
from suites.memblock.lsq.vlq.types import Dispatch as LoadDispatch
from suites.memblock.lsq.vsq.types import Dispatch as StoreDispatch
from suites.memblock.lsq.raw.types import SqPtr
from .codec import load_public_view, ports, store_public_view
from .store_perf import StorePerfHistory


def rob_code(pointer):
    return (int(pointer["flag"]) * 160 + pointer["value"]) * 2 + int(not pointer["former"])


def request_rob(values, prefix):
    return dict(flag=bool(values[prefix + "robIdx_flag"]), value=values[prefix + "robIdx_value"],
                former=bool(values[prefix + "robIdx_isFormer"]))


class WrapperModel:
    def __init__(self):
        self.load, self.store = LoadQueueModel(), StoreQueueModel()
        self.serial, self.jobs, self.sequence = None, {}, 0
        self.busy, self.perf, self.perf_delay = None, {}, {}
        self.store_perf = StorePerfHistory()
        self.edges = 0
        self.unimplemented_outputs = ()

    def connected(self, inp, *, before=False):
        store = replace(store_public_view(inp), dispatch=tuple(StoreDispatch(d.valid and bool(d.need_alloc & 2),
                        bool(d.need_alloc & 2), d.rob, d.flows, d.store_end) for d in inp.dispatch))
        sv, sm = self.store.expected(store, before=before)
        def ptr(prefix, fallback=0):
            if prefix + "value" not in sv:
                return SqPtr.encode(fallback)
            return SqPtr(bool(sv[prefix + "first_flag"]), bool(sv[prefix + "second_flag"]), sv[prefix + "value"])
        load = replace(load_public_view(inp), dispatch=tuple(LoadDispatch(d.valid and bool(d.need_alloc & 1), d.rob,
                       d.load_start, d.flows) for d in inp.dispatch),
                       address_ready=ptr("io_toLoadQueue_stAddrReadySqPtr_"), data_ready=ptr("io_toLoadQueue_stDataReadySqPtr_"),
                       address_bits=sum(sv[f"io_toLoadQueue_stAddrReadyVec_{slot}"] << slot for slot in range(64)),
                       data_bits=sum(sv[f"io_toLoadQueue_stDataReadyVec_{slot}"] << slot for slot in range(64)),
                       dequeue=ptr("io_sqDeqPtr_"), upper=ptr("io_physicalUpperSqIdx_", 64), sq_empty=bool(sv.get("io_sqEmpty", 1)))
        lv = self.load.expected(load)
        lp, sp = "io_uncache_req_", "io_toUncacheBuffer_req_"
        lvalid, svalid = bool(lv[lp + "valid"]), bool(sv[sp + "valid"])
        load_first = False
        if lvalid and svalid:
            distance = (rob_code(request_rob(sv, sp + "bits_")) - rob_code(request_rob(lv, lp + "bits_"))) % 640
            assert distance != 320, "ambiguous ROB half-ring is not normal mixed traffic"
            load_first = 0 < distance < 320
        elif lvalid:
            load_first = True
        serial = None if inp.reset else self.serial
        selected = "load" if load_first else "store"
        bus_valid = serial is None and (lvalid if load_first else svalid)
        # Both inputs below are frozen BEFORE child advance. The public ready
        # is delivered to exactly one chosen real child, only while idle.
        load = replace(load, bus=replace(load.bus, ready=inp.bus.ready and serial is None and load_first,
                       ack=inp.bus.ack and inp.bus.ack_to_load, response=inp.bus.response and inp.bus.response_to_load))
        store = replace(store, uncache_ready=inp.bus.ready and serial is None and not load_first,
                        uncache_ack_valid=inp.bus.ack and not inp.bus.ack_to_load, uncache_ack_to_load=inp.bus.ack_to_load,
                        uncache_response=inp.bus.response and not inp.bus.response_to_load)
        return load, store, lv, sv, sm, selected, bus_valid

    @staticmethod
    def mapped(name, kind):
        if name.startswith("io_perf_"):
            return None
        if kind == "load":
            if name == "io_rob_mmioBusy" or name.startswith("io_uncache_req_"):
                return None
            for old, new in (("io_lqDeq_", "io_toLsqEnqCtrl_lqDeq_"), ("io_lqRedirect_", "io_toLsqEnqCtrl_lqRedirectPtr_"),
                             ("io_exceptionInfo_", "io_ldExceptionInfo_")):
                if name.startswith(old):
                    return new + name[len(old):]
            if name == "io_lqRecoverStall":
                return "io_toLsqEnqCtrl_lqRecoverStall"
        else:
            if name == "io_toRob_mmioBusy" or name.startswith(("io_toUncacheBuffer_", "io_physicalUpperSqIdx_",
                                                                "io_toLoadQueue_stDataReady", "io_toLoadQueue_stAddrReadyVec_")):
                return None
            for old, new in (("io_writeToSbuffer_", "io_sbuffer_"), ("io_writeBack_", "io_mmioStout_"),
                             ("io_toDCache_req_", "io_cmoOpReq_"), ("io_toDCache_resp_", "io_cmoOpResp_"),
                             ("io_fromStoreUnit_", "io_sta_"), ("io_exceptionInfo_", "io_stExceptionInfo_"),
                             ("io_toLoadQueue_stAddrReadySqPtr_", "io_issuePtrExt_")):
                if name.startswith(old):
                    return new + name[len(old):]
            controls = {"io_sbufferCtrl_req_flush": "io_flushSbuffer_valid", "io_sbufferCtrl_req_forceWrite": "io_force_write",
                        "io_sbufferCtrl_req_physicalStoreQueueFull": None}
            if name in controls:
                return controls[name]
        return name

    def expected(self, inp, *, before=False):
        _, _, load, store, sm, selected, bus_valid = self.connected(inp, before=before)
        values, masks = {}, {}
        for kind, child in (("load", load), ("store", store)):
            for name, value in child.items():
                target = self.mapped(name, kind)
                if target is None:
                    continue
                assert target in ports()["output"], ("unmapped actual output boundary", kind, name, target)
                assert target not in values or values[target] == value
                values[target] = value
                if kind == "store" and name in sm:
                    masks[target] = sm[name]
        values["io_uncache_req_valid"] = int(bus_valid)
        if bus_valid:
            child, prefix = (load, "io_uncache_req_bits_") if selected == "load" else (store, "io_toUncacheBuffer_req_bits_")
            for field in ("robIdx_flag", "robIdx_value", "robIdx_isFormer", "cmd", "addr", "vaddr", "data", "mask", "id", "nc", "memBackTypeMM"):
                if selected == "load" and field == "data":
                    continue  # Actual load request data is DontCare, not zero.
                # StoreQueue's constant command port was optimized away.
                # The REAL wrapper supplies literal M_XWR (SV:4393), not a
                # hidden/missing child output that can be sampled or driven.
                value = 1 if selected == "store" and field == "cmd" else child[prefix + field]
                values["io_uncache_req_bits_" + field] = value
                if selected == "store" and prefix + field in sm:
                    masks["io_uncache_req_bits_" + field] = sm[prefix + field]
        if self.busy is not None:
            values["io_rob_mmioBusy"] = self.busy
        values.update(self.perf)
        values.update(self.store_perf.expected())
        return values, masks

    def safety(self, inp, actual):
        store = self.connected(inp)[1]
        renamed = {"io_forward_" + key[len("io_forward_"):]: value for key, value in actual.items() if key.startswith("io_forward_")}
        return self.store.safety(store, renamed)

    def advance(self, inp):
        load, store, lv, sv, _, selected, bus_valid = self.connected(inp, before=True)
        old_feedback = dict(address=asdict(load.address_ready), data=asdict(load.data_ready), address_bits=load.address_bits,
                            data_bits=load.data_bits, dequeue=asdict(load.dequeue), upper=asdict(load.upper), empty=load.sq_empty)
        next_perf = {name: value for name, value in lv.items() if name.startswith("io_perf_")}
        # Sample the OLD public Store history before either branch advances.
        store_perf = self.store_perf.advance(self.store.physical, self.store.connected(store)[1])
        self.busy = int(lv["io_rob_mmioBusy"] or sv["io_toRob_mmioBusy"])
        self.perf, self.perf_delay = self.perf_delay, next_perf
        accepted = None
        if inp.reset:
            self.serial, self.jobs = None, {}
        else:
            if bus_valid and inp.bus.ready:
                source, prefix = (lv, "io_uncache_req_bits_") if selected == "load" else (sv, "io_toUncacheBuffer_req_bits_")
                self.sequence += 1
                accepted = self.sequence
                self.jobs[accepted] = dict(kind=selected, mid=source[prefix + "id"], sid=None,
                                           rob=request_rob(source, prefix), addr=source[prefix + "addr"])
                if not (inp.bus.outstanding and source[prefix + "nc"]):
                    assert self.serial is None
                    self.serial = accepted
            if inp.bus.ack:
                kind = "load" if inp.bus.ack_to_load else "store"
                hits = [uid for uid, job in self.jobs.items() if job["kind"] == kind and job["mid"] == inp.bus.mid and job["sid"] is None]
                assert len(hits) == 1, "ack must name one previously accepted request of its own direction"
                assert not any(job["sid"] == inp.bus.sid for job in self.jobs.values()), "SID still belongs to an outstanding response"
                self.jobs[hits[0]]["sid"] = inp.bus.sid
            if inp.bus.response:
                kind = "load" if inp.bus.response_to_load else "store"
                hits = [uid for uid, job in self.jobs.items() if job["kind"] == kind and job["sid"] == inp.bus.response_id]
                assert len(hits) == 1, "response must bind its original direction/SID, not current selection"
                uid = hits[0]
                del self.jobs[uid]
                if self.serial == uid:
                    self.serial = None
        # Both immutable connected inputs were built above. Neither reference
        # may see the other reference's newly advanced output at this edge.
        lc, sc = self.load.advance(load), self.store.advance(store)
        self.edges += 1
        return dict(load=lc, store=sc, sq_feedback_before=old_feedback, selected=selected, bus_accepted=accepted,
                    serial=self.serial, external_bus_jobs=self.jobs.copy(), store_perf_event=store_perf,
                    unimplemented_outputs=self.unimplemented_outputs)
