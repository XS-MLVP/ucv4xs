from .types import Inputs, Outputs, Query, QueuePtr, Redirect, Release, Response, RobPtr


class Ports:
    def __init__(self, dut, spec):
        self.dut, self.spec = dut, spec
        names = ("req_valid", "req_bits_robIdx_flag", "req_bits_robIdx_value", "req_bits_robIdx_isFormer",
                 "req_bits_lqIdx_flag", "req_bits_lqIdx_value", "req_bits_paddr", "req_bits_dataValid", "req_bits_nc",
                 "revokeLastCycle", "revokeLastLastCycle")
        self.query = tuple(tuple(getattr(dut, f"io_query_{i}_{name}") for name in names) for i in range(spec["query_width"]))
        self.ready = tuple(getattr(dut, f"io_query_{i}_req_ready") for i in range(spec["query_width"]))
        self.response = tuple((getattr(dut, f"io_query_{i}_resp_valid"), getattr(dut, f"io_query_{i}_resp_bits_nuke"))
                              for i in range(spec["query_width"]))
        self.redirect = tuple(getattr(dut, "io_redirect_" + name) for name in
                              ("valid", "bits_robIdx_flag", "bits_robIdx_value", "bits_robIdx_isFormer", "bits_level"))

    @property
    def driven(self):
        return (self.dut.reset, self.dut.io_release_valid, self.dut.io_release_bits_paddr,
                self.dut.io_ldWbPtr_flag, self.dut.io_ldWbPtr_value, *self.redirect, *(s for lane in self.query for s in lane))

    def sample(self, event):
        queries, revoke_last, revoke_older = [], [], []
        for lane in self.query:
            valid, rf, rv, former, qf, qv, address, data, nc, one, two = (s.U() for s in lane)
            queries.append(Query(bool(valid), RobPtr(bool(rf), rv, bool(former)), QueuePtr(bool(qf), qv), address, bool(data), bool(nc)))
            revoke_last.append(bool(one))
            revoke_older.append(bool(two))
        valid, flag, value, former, level = (s.U() for s in self.redirect)
        inp = Inputs(tuple(queries), tuple(revoke_last), tuple(revoke_older),
                     QueuePtr(bool(self.dut.io_ldWbPtr_flag.U()), self.dut.io_ldWbPtr_value.U()),
                     Redirect(bool(valid), RobPtr(bool(flag), value, bool(former)), bool(level)),
                     Release(bool(self.dut.io_release_valid.U()), self.dut.io_release_bits_paddr.U()), bool(self.dut.reset.U()))
        out = Outputs(tuple(bool(s.U()) for s in self.ready), tuple(Response(bool(v.U()), bool(n.U())) for v, n in self.response),
                      bool(self.dut.io_lqFull.U()), self.dut.io_perf_0_value.U(), self.dut.io_perf_1_value.U())
        return inp, out
