from .types import (BusRequest, DataOutput, FaultReport, IdResponse, Inputs, Outputs, QueuePtr, Redirect,
                    Request, Response, RobPtr, SOURCE_EXCEPTION_BITS, Wakeup)

REQUEST_NAMES = (
    "valid", "bits_uop_robIdx_flag", "bits_uop_robIdx_value", "bits_uop_robIdx_isFormer", "bits_uop_lqIdx_flag", "bits_uop_lqIdx_value",
    "bits_vaddr", "bits_fullva", "bits_paddr", "bits_gpaddr", "bits_mask", "bits_nc", "bits_mmio", "bits_memBackTypeMM",
    "bits_isHyper", "bits_isForVSnonLeafPTE", *(f"bits_uop_exceptionVec_{bit}" for bit in SOURCE_EXCEPTION_BITS))


class Ports:
    def __init__(self, dut, spec):
        self.dut, self.spec = dut, spec
        self.request = tuple(getattr(dut, "io_req_" + name) for name in REQUEST_NAMES)
        self.pending = tuple(getattr(dut, "io_rob_pendingPtr_" + name) for name in ("flag", "value", "isFormer"))
        self.redirect = tuple(getattr(dut, "io_redirect_" + name) for name in ("valid", "bits_robIdx_flag", "bits_robIdx_value", "bits_robIdx_isFormer", "bits_level"))
        self.id_response = tuple(getattr(dut, "io_uncache_idResp_" + name) for name in ("valid", "bits_mid", "bits_sid"))
        self.response = tuple(getattr(dut, "io_uncache_resp_" + name) for name in ("valid", "bits_data", "bits_error", "bits_nderr"))
        self.ready = (dut.io_uncache_req_ready, dut.io_mmioOut_ready, dut.io_ncOut_ready)
        self.wake_ready = tuple(getattr(dut, "io_" + kind + "Wakeup_ready") for kind in ("mmio", "nc")) if spec["wakeup_backpressure"] else ()
        bus_names = ("valid", "bits_robIdx_flag", "bits_robIdx_value", "bits_robIdx_isFormer", "bits_addr", "bits_vaddr", "bits_mask", "bits_nc", "bits_memBackTypeMM")
        self.bus = tuple(getattr(dut, "io_uncache_req_" + name) for name in bus_names)
        self.wakes = tuple(tuple(getattr(dut, f"io_{kind}Wakeup_{name}") for name in ("valid", "bits_flag", "bits_value")) for kind in ("mmio", "nc"))
        self.outs = []
        for kind in ("mmio", "nc"):
            names = ("valid", "bits_uop_lqIdx_flag", "bits_uop_lqIdx_value", "bits_debug_paddr" if kind == "mmio" else "bits_paddr",
                     "bits_uop_exceptionVec_19", "bits_uop_exceptionVec_5")
            signals = tuple(getattr(dut, f"io_{kind}Out_{name}") for name in names)
            data = dut.io_mmioRawData_lqData if kind == "mmio" else dut.io_ncOut_bits_data
            self.outs.append((*signals, data))
        self.fault_bits = (*SOURCE_EXCEPTION_BITS, 19, 5)
        fault_names = ("valid", "bits_uop_robIdx_flag", "bits_uop_robIdx_value", "bits_uop_robIdx_isFormer", "bits_fullva", "bits_gpaddr",
                       "bits_isHyper", "bits_isForVSnonLeafPTE", *(f"bits_uop_exceptionVec_{bit}" for bit in self.fault_bits))
        self.fault = tuple(getattr(dut, "io_exception_" + name) for name in fault_names)

    @property
    def driven(self):
        return (self.dut.reset, *self.request, *self.pending, *self.redirect, *self.id_response, *self.response, *self.ready, *self.wake_ready)

    def sample(self, event):
        values = [s.U() for s in self.request]
        valid, rf, rv, former, lf, lv, va, full, pa, gpa, mask, nc, mmio, backed, hyper, leaf, *exception = values
        q = Request(bool(valid), RobPtr(bool(rf), rv, bool(former)), QueuePtr(bool(lf), lv), va, full, pa, gpa, mask,
                    bool(nc), bool(mmio), bool(backed), bool(hyper), bool(leaf), sum(value << bit for value, bit in zip(exception, SOURCE_EXCEPTION_BITS, strict=True)))
        pf, pv, former = (s.U() for s in self.pending)
        valid, rf, rv, former_r, level = (s.U() for s in self.redirect)
        valid_i, mid, sid = (s.U() for s in self.id_response)
        valid_r, data, error, nderr = (s.U() for s in self.response)
        ready, mmio_ready, nc_ready = (bool(s.U()) for s in self.ready)
        mmio_wake, nc_wake = (bool(s.U()) for s in self.wake_ready) if self.wake_ready else (True, True)
        inp = Inputs(q, RobPtr(bool(pf), pv, bool(former)), Redirect(bool(valid), RobPtr(bool(rf), rv, bool(former_r)), bool(level)),
                     ready, IdResponse(bool(valid_i), mid, sid), Response(bool(valid_r), data, bool(error), bool(nderr)),
                     mmio_wake, nc_wake, mmio_ready, nc_ready, bool(self.dut.reset.U()))
        valid, rf, rv, former, pa, va, mask, nc, backed = (s.U() for s in self.bus)
        bus = BusRequest(bool(valid), RobPtr(bool(rf), rv, bool(former)), pa, va, mask, bool(nc), bool(backed))
        wakes = []
        for signals in self.wakes:
            valid, flag, value = (s.U() for s in signals)
            wakes.append(Wakeup(bool(valid), QueuePtr(bool(flag), value)))
        outs = []
        for signals in self.outs:
            valid, flag, value, pa, error, nderr, data = (s.U() for s in signals)
            outs.append(DataOutput(bool(valid), QueuePtr(bool(flag), value), pa, data, bool(error), bool(nderr)))
        valid, rf, rv, former, full, gpa, hyper, leaf, *exception = (s.U() for s in self.fault)
        fault = FaultReport(bool(valid), RobPtr(bool(rf), rv, bool(former)), full, gpa, bool(hyper), bool(leaf),
                            sum(value << bit for value, bit in zip(exception, self.fault_bits, strict=True)))
        out = Outputs(bool(self.dut.io_flush.U()), bool(self.dut.io_mmioSelect.U()), bool(self.dut.io_slaveId_valid.U()),
                      self.dut.io_slaveId_bits.U(), bus, *wakes, *outs, fault)
        return inp, out
