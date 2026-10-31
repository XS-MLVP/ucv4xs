from .types import Observation


class Ports:
    def __init__(self, dut, spec):
        self.dut, self.spec = dut, spec
        self.enq = tuple(getattr(dut, f"io_enq_{i}") for i in range(spec["enqueue_width"]))

    @property
    def driven(self):
        return (self.dut.reset, self.dut.io_deq, self.dut.io_ready, *self.enq)

    def sample(self, event):
        return Observation(tuple(s.U() for s in self.enq), self.dut.io_deq.U(), self.dut.io_ready.U(),
                           bool(self.dut.reset.U()), self.dut.io_out.U())
