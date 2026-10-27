"""One immutable owner and semantic protocol phases; no DUT state reads."""
from .types import BusRequest, Change, DataOutput, FaultReport, Outputs, Owner, Request, RobPtr, Wakeup


def is_younger(left, right, entries=160):
    def slot(ptr):
        if not 0 <= ptr.value < entries:
            raise ValueError("ROB pointer outside configured entries")
        return 2 * (int(ptr.flag) * entries + ptr.value) + int(not ptr.former)
    delta = (slot(left) - slot(right)) % (4 * entries)
    if delta == 2 * entries:
        raise ValueError("ambiguous ROB half-ring age")
    return 0 < delta < 2 * entries


class UncacheEntryModel:
    def __init__(self, spec):
        self.spec = spec
        self.edge = self.uid_sequence = 0
        self.reset_kind = None
        self.restart()

    def restart(self):
        self.owner = None
        self.phase = "holding"
        self.pending = RobPtr()
        self.slave_id = None
        self.deferred = False
        self.response_data = 0
        self.error = self.nderr = False
        self.exception = FaultReport()

    def need_flush(self, inp):
        if self.owner is None or not inp.redirect.valid:
            return False
        rob, red = self.owner.request.rob, inp.redirect
        return is_younger(rob, red.rob) or red.flush_self and rob == red.rob

    def outputs_for(self, inp):
        owner = self.owner
        q = owner.request if owner else Request()
        cancel = self.need_flush(inp)
        bus_valid = owner is not None and self.phase == "request" and not cancel
        wake_active = owner is not None and self.phase == "wakeup" and not self.deferred
        out_active = owner is not None and self.phase == "output"
        consumed = out_active and (inp.nc_ready if q.nc else inp.mmio_ready)
        flush = False
        if owner is not None:
            if self.phase in ("holding", "request"):
                flush = cancel
            elif self.phase == "response":
                flush = inp.response.valid and (cancel or self.deferred)
            elif self.phase == "wakeup":
                flush = cancel or self.deferred
            elif self.phase == "output":
                flush = cancel or consumed
        mask = (q.mask >> (8 if q.paddr & 8 else 0)) & 0xFF
        bus = BusRequest(bus_valid, q.rob, q.paddr, q.vaddr, mask, q.nc, q.memory_backed)
        mmio = DataOutput(out_active and not q.nc, q.lq, q.paddr, self.response_data, self.error, self.nderr)
        nc = DataOutput(out_active and q.nc, q.lq, q.paddr, self.response_data, self.error, self.nderr)
        return Outputs(flush, owner is not None and self.phase != "holding" and q.mmio,
                       self.slave_id is not None, self.slave_id or 0, bus,
                       Wakeup(wake_active and q.mmio, q.lq), Wakeup(wake_active and q.nc, q.lq), mmio, nc, self.exception)

    def advance(self, inp):
        self.edge += 1
        old = self.owner
        phase_before = self.phase if old else "empty"
        if inp.reset:
            if inp.request.valid or inp.id_response.valid or inp.response.valid or inp.redirect.valid:
                raise ValueError("UncacheEntry reset requires idle transaction inputs")
            self.reset_kind = self.reset_kind or ("active" if old else "initial")
            self.restart()
            return Change(before=old, phase_before=phase_before, reset_kind=self.reset_kind)
        self.reset_kind = None
        out = self.outputs_for(inp)
        cancel, deferred_before = self.need_flush(inp), self.deferred
        issued = out.bus.valid and inp.bus_ready
        mmio_ready = inp.mmio_wake_ready if self.spec["wakeup_backpressure"] else True
        nc_ready = inp.nc_wake_ready if self.spec["wakeup_backpressure"] else True
        woke = out.mmio_wakeup.valid and mmio_ready or out.nc_wakeup.valid and nc_ready
        consumed = out.mmio.valid and inp.mmio_ready or out.nc.valid and inp.nc_ready
        bound = old is not None and inp.id_response.valid and inp.id_response.mid == self.spec["entry_id"]
        if inp.request.valid:
            if old is not None:
                raise ValueError("Valid-only allocation would overwrite an owned entry")
            q = inp.request
            if q.mmio == q.nc or not 0 <= q.lq.value < self.spec["lq_entries"]:
                raise ValueError("legal entry allocation requires exactly one MMIO/NC type and legal LQ")
            if inp.redirect.valid and (is_younger(q.rob, inp.redirect.rob) or inp.redirect.flush_self and q.rob == inp.redirect.rob):
                raise ValueError("parent must suppress an already-canceled new entry allocation")
        if bound and self.phase not in ("response", "wakeup", "output") and not issued:
            raise ValueError("correct ID acknowledgement before actual bus acceptance")
        if inp.response.valid and (old is None or self.phase != "response" or self.slave_id is None):
            raise ValueError("data response must target an issued, ID-bound owner waiting for response")
        exception = FaultReport()
        if consumed:
            q = old.request
            errors = q.exceptions | (int(self.nderr) << 5) | (int(self.error) << 19)
            exception = FaultReport(True, q.rob, q.fullva, q.gpaddr, q.hyper, q.nonleaf, errors)
        allocated = None
        if out.flush:
            self.owner = None
            self.phase = "holding"
            self.slave_id = None
            self.deferred = False
        else:
            if old is not None:
                if self.phase == "holding":
                    q = old.request
                    if q.nc or not is_younger(q.rob, self.pending):
                        self.phase = "request"
                elif self.phase == "request" and issued:
                    self.phase = "response"
                elif self.phase == "response" and inp.response.valid:
                    self.phase = "wakeup"
                elif self.phase == "wakeup" and woke:
                    self.phase = "output"
            self.deferred |= cancel
            if inp.request.valid:
                self.uid_sequence += 1
                allocated = self.owner = Owner(self.uid_sequence, inp.request)
                self.slave_id = None
                self.error = self.nderr = False
            elif bound:
                self.slave_id = inp.id_response.sid
        if inp.response.valid:
            self.response_data, self.error, self.nderr = inp.response.data, inp.response.error, inp.response.nderr
        self.pending, self.exception = inp.pending, exception
        return Change(old, allocated, phase_before, self.phase if self.owner else "empty", issued, bound,
                      inp.response.valid, bool(woke), bool(consumed), bool(out.flush), bool(cancel or deferred_before),
                      deferred_before, self.deferred)
