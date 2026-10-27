from .types import Observation, Query, Write


class Ports:
    def __init__(self, dut, spec):
        self.dut, self.spec = dut, spec
        self.wen = tuple(getattr(dut, f"io_wen_{i}") for i in range(spec["write_width"]))
        self.waddr = tuple(getattr(dut, f"io_waddr_{i}") for i in range(spec["write_width"]))
        self.wdata = tuple(getattr(dut, f"io_wdata_{i}") for i in range(spec["write_width"]))
        self.qdata, self.qline, self.masks = [], [], []
        for name in spec["queries"]:
            family, index = name.rsplit("_", 1)
            self.qdata.append(getattr(dut, f"io_{family}data_{index}"))
            self.qline.append(getattr(dut, f"io_violationCheckLine_{index}")
                              if spec["kind"] == "address_line" else None)
            self.masks.append(tuple(getattr(dut, f"io_{family}mask_{index}_{i}") for i in range(spec["size"])))

    @property
    def driven(self):
        return (*self.wen, *self.waddr, *self.wdata, *self.qdata, *(s for s in self.qline if s is not None))

    def sample(self, event):
        writes = tuple(Write(a.U(), d.U(), bool(e.U())) for e, a, d in zip(self.wen, self.waddr, self.wdata, strict=True))
        queries = tuple(Query(d.U(), bool(line.U()) if line is not None else False)
                        for d, line in zip(self.qdata, self.qline, strict=True))
        masks = tuple(sum(s.U() << i for i, s in enumerate(port)) for port in self.masks)
        return Observation(writes, queries, masks)
