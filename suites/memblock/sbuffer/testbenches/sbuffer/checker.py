"""Pure writeback ledger: identities originate in accepted enqueue transactions."""
from suites.memblock.sbuffer.testbenches.sbuffer.model import BYTES
from suites.memblock.sbuffer.testbenches.sbuffer.model import LANES
from suites.memblock.sbuffer.testbenches.sbuffer.model import LINES
from suites.memblock.sbuffer.testbenches.sbuffer.model import SbufferModel
from suites.memblock.sbuffer.testbenches.sbuffer.transactions import Event
from suites.memblock.sbuffer.testbenches.sbuffer.transactions import Request
from suites.memblock.sbuffer.testbenches.sbuffer.transactions import Writeback


class WritebackLedger:
    def __init__(self, model: SbufferModel):
        self.model = model
        self.reserved = {}
        self.offered = {}
        self.pending = {}
        self.retries = {}
        self.attempts = {}
        self.events = []
        self.enqueue_offered = 0
        self.enqueue_accepted = 0

    def _line(self, uid):
        matches = [line for line in self.model.lines if line.uid == uid]
        assert len(matches) == 1, ('unknown model line identity', uid)
        return matches[0]

    @staticmethod
    def _matches(request, line):
        if (request.addr, request.vaddr, request.mask) != (line.ptag << 6, line.vtag << 6, line.line_mask()):
            return False
        for byte in range(BYTES * LANES):
            if (request.mask >> byte) & 1:
                if ((request.data >> (8 * byte)) & 255) != line.data[byte // BYTES][byte % BYTES]:
                    return False
        return True

    def inspect(self, request: Request) -> Writeback:
        assert 0 <= request.id < LINES, ('writeback slot out of range', request)
        assert request.addr & 63 == 0 and request.vaddr & 63 == 0, ('unaligned writeback address', request)
        assert request.id not in self.pending, ('writeback slot still awaiting response', request.id)
        if request.id in self.reserved:
            # An accepted retry already has an independent input identity. A
            # younger active line can legally have identical address/data/mask;
            # re-matching both by payload would falsely call that ambiguous.
            line = self._line(self.reserved[request.id])
            assert request.id in self.retries, ('writeback not authorized to retry', request.id)
            assert self._matches(request, line), ('retry payload must match its reserved input line', request)
            previous = self.retries[request.id]
            assert (request.addr, request.vaddr, request.mask) == (previous.addr, previous.vaddr, previous.mask), (
                'retry identity changed', request, previous)
        elif request.id in self.offered:
            # This DUT's output pipeline removes the line from the active merge
            # set before the external DCache handshake. Keep that public offer
            # separate from an accepted response obligation.
            line = self._line(self.offered[request.id])
            assert self._matches(request, line), ('offered writeback payload changed identity', request)
        else:
            inflight_tags = {line.ptag for line in self.model.lines if line.inflight}
            matches = [line for line in self.model.lines if not line.inflight
                       and line.ptag not in inflight_tags and self._matches(request, line)]
            assert len(matches) == 1, ('writeback payload must match one eligible live input line', request, len(matches))
            line = matches[0]
            assert line.uid not in self.reserved.values(), ('line changed writeback slot', line.uid)
            assert not line.inflight, ('inflight line has no authorized replay', line.uid)
            assert not any(item.ptag == line.ptag and item.inflight for item in self.model.lines), (
                'same-block writeback before prior completion', line.uid)
        valid_data = sum(((request.data >> (8 * byte)) & 255) << (8 * byte)
                         for byte in range(BYTES * LANES) if (request.mask >> byte) & 1)
        return Writeback(request.id, request.addr, request.vaddr, request.mask, valid_data,
                         line.uid, self.attempts.get(line.uid, 0) + 1)

    def accept(self, request: Request, tick: int) -> Writeback:
        snap = self.inspect(request)
        self.reserved[snap.id] = snap.uid
        self.pending[snap.id] = snap
        self.offered.pop(snap.id, None)
        self.retries.pop(snap.id, None)
        self.attempts[snap.uid] = snap.attempt
        self.model.mark_inflight(self._line(snap.uid))
        self.events.append(Event('accepted', snap.uid, snap.attempt, snap.id, tick))
        return snap

    def offer(self, request: Request):
        snap = self.inspect(request)
        if snap.id not in self.reserved:
            self.offered[snap.id] = snap.uid
            self.model.mark_inflight(self._line(snap.uid))
        return snap

    def require_pending(self, snap: Writeback):
        assert self.pending.get(snap.id) == snap, ('response has stale or unaccepted identity', snap)

    def respond(self, slot: int, kind: str, tick: int):
        assert kind in ('hit', 'replay')
        assert slot in self.pending, ('response without accepted writeback', slot, kind)
        snap = self.pending.pop(slot)
        line = self._line(snap.uid)
        if kind == 'hit':
            self.model.on_hit(line)
            del self.reserved[slot]
        else:
            self.model.on_replay(line)
            self.retries[slot] = snap
        self.events.append(Event(kind, snap.uid, snap.attempt, slot, tick))

    def observe(self, observation, tick: int):
        if observation.reset:
            self.reset(tick)
            return None
        assert observation.hit is None or observation.hit != observation.replay, (
            'one accepted writeback cannot hit and replay simultaneously')
        for slot in (observation.hit, observation.replay):
            if slot is not None:
                assert slot in self.pending, ('response without previously accepted writeback', slot)
        accepted = None
        if observation.request is not None:
            if observation.request_fire:
                accepted = self.accept(observation.request, tick)
            else:
                self.offer(observation.request)
        if observation.hit is not None:
            self.respond(observation.hit, 'hit', tick)
        if observation.replay is not None:
            self.respond(observation.replay, 'replay', tick)
        self.enqueue_offered += len(observation.enqueues)
        incoming = [req for _, req, ready in observation.enqueues if ready]
        self.enqueue_accepted += len(incoming)
        self.model.enqueue(incoming)
        return accepted

    def reset(self, tick: int):
        for slot, uid in self.reserved.items():
            self.events.append(Event('reset_cancelled', uid, self.attempts[uid], slot, tick))
        self.reserved.clear()
        self.pending.clear()
        self.retries.clear()
        self.offered.clear()
        self.model.reset()

    def finish(self):
        assert not self.reserved and not self.pending and not self.retries, (
            'uncompleted writeback obligations', self.pending, self.retries)
