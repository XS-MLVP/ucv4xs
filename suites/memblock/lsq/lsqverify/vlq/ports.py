from .types import Dispatch, Inputs, Observation, Outputs, QueuePtr, Redirect, RobPtr, Writeback


class Ports:
    def __init__(self, dut, spec):
        self.dut, self.spec = dut, spec
        names = ("valid", "bits_robIdx_flag", "bits_robIdx_value", "bits_robIdx_isFormer",
                 "bits_lqIdx_flag", "bits_lqIdx_value", "bits_numLsElem")
        self.dispatch = tuple(tuple(getattr(dut, f"io_enq_req_{i}_{name}") for name in names)
                              for i in range(spec["dispatch_width"]))
        names = ("valid", "bits_uop_lqIdx_value", "bits_updateAddrValid", "bits_rep_info_need_rep")
        self.writebacks = tuple(tuple(getattr(dut, f"io_ldin_{i}_{name}") for name in names)
                                for i in range(spec["writeback_width"]))
        self.redirect = tuple(getattr(dut, "io_redirect_" + name) for name in
                              ("valid", "bits_robIdx_flag", "bits_robIdx_value", "bits_robIdx_isFormer", "bits_level"))

    @property
    def driven(self):
        return (self.dut.reset, *self.redirect, *(s for lane in self.dispatch for s in lane),
                *(s for lane in self.writebacks for s in lane))

    def sample(self, event):
        dispatch = []
        for lane in self.dispatch:
            valid, rf, rv, former, qf, qv, flows = (s.U() for s in lane)
            dispatch.append(Dispatch(bool(valid), RobPtr(bool(rf), rv, bool(former)), QueuePtr(bool(qf), qv), flows))
        writebacks = tuple(Writeback(bool(v.U()), a.U(), bool(u.U()), bool(r.U())) for v, a, u, r in self.writebacks)
        v, f, value, former, level = (s.U() for s in self.redirect)
        redirect = Redirect(bool(v), RobPtr(bool(f), value, bool(former)), bool(level))
        inp = Inputs(tuple(dispatch), writebacks, redirect, bool(self.dut.reset.U()))
        out = Outputs(QueuePtr(bool(self.dut.io_ldWbPtr_flag.U()), self.dut.io_ldWbPtr_value.U()),
                      bool(self.dut.io_lqEmpty.U()), bool(self.dut.io_lqDeq_valid.U()), self.dut.io_lqDeq_bits.U(),
                      bool(self.dut.io_lqRedirect_valid.U()),
                      QueuePtr(bool(self.dut.io_lqRedirect_bits_flag.U()), self.dut.io_lqRedirect_bits_value.U()),
                      bool(self.dut.io_lqRecoverStall.U()))
        return Observation(inp, out)
