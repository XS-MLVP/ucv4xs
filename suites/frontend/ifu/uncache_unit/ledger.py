"""Input-established UIDs; count fires only once at their actual sampled edge."""
from dataclasses import replace

from suites.frontend.ifu.model.uncache import IDLE, IO, NC, WAIT_RESP

from .types import Events, ReadRequest, RequestRecord, Status


class RequestLedger:
    def __init__(self):
        self.epoch = 0
        self.records = {}
        self.active_uid = self.pulse_uid = None
        self.seen_replies = set()
        self.offered_cycles = self.req_fires = self.accepted = self.flushed_on_accept = 0
        self.issued = self.completed = self.cancelled = self.response_fires = self.ignored_responses = 0

    def offer(self, request, scope):
        uid = len(self.records) + 1
        self.records[uid] = RequestRecord(uid, self.epoch, request, scope)
        return uid

    def validate_producer(self, inputs, phase, response_uid):
        if inputs.req_valid and (inputs.req_pbmt == 3 or
                not (inputs.req_is_mmio or inputs.req_pbmt in (NC, IO))):
            raise ValueError('IFU producer requires MMIO/NC/IO, never reserved PBMT')
        if not inputs.from_valid:
            if response_uid is not None:
                raise ValueError('response UID requires a valid response')
            return None
        if response_uid is None:
            raise ValueError('producer response requires an explicit issued UID; use reply/read')
        uid = response_uid
        if type(uid) is not int or uid not in self.records:
            raise ValueError('bus response has no known issued request UID')
        record = self.records[uid]
        if record.scope != 'producer':
            raise ValueError('port-characterization request has no producer reply provenance')
        if uid in self.seen_replies:
            raise ValueError('duplicate bus response UID')
        if record.issued_tick is None:
            raise ValueError('bus response arrived before its request was issued')
        if uid != self.active_uid or phase != WAIT_RESP:
            if record.state != 'cancelled' or phase == WAIT_RESP:
                raise ValueError('tagless response cannot be attributed to this live generation')
        resend = self.expected_resend(record.request, inputs.from_data, inputs.from_corrupt)
        if inputs.from_need_resend != resend:
            raise ValueError('InstrUncache producer needResend must match clean nonRVC cross-page data')
        return uid

    @staticmethod
    def expected_resend(request, data, corrupt):
        return int((request.paddr & 0xFFF) == 0xFFE and not corrupt and (data & 3) == 3)

    def consume(self, inputs, before, after, tick, offer_uid, response_uid, reason):
        previous = self.pulse_uid
        assert bool(before.resp_valid) == (previous is not None), 'missing or duplicate prior completion pulse'
        active, issued_uid, completed_uid = self.active_uid, None, None
        cancelled = []
        if inputs.req_valid:
            self.offered_cycles += 1
        if before.to_valid and inputs.to_ready:
            assert active is not None, 'bus issue without an accepted request'
            record = self.records[active]
            assert record.issued_tick is None, 'duplicate issue of a held bus request'
            assert before.to_paddr == record.request.paddr, 'bus issue lost captured input address'
            assert before.to_mem_back_mm == int(not record.request.is_mmio), 'bus issue lost memory-back type'
            assert before.to_mem_page_nc == int(record.request.pbmt == NC), 'bus issue lost PBMT identity'
            self.records[active] = replace(record, state='issued', issued_tick=tick)
            self.issued += 1
            issued_uid = active
        if inputs.from_valid:
            self.response_fires += 1  # Ready is the proven constant1, including ignored replies.
            if response_uid is not None:
                self.seen_replies.add(response_uid)
        if after.resp_valid:
            assert active is not None and inputs.from_valid and not inputs.flush, 'unsolicited completion pulse'
            record = self.records[active]
            assert record.issued_tick is not None, 'completion before bus issue'
            assert response_uid in (None, active), 'completion UID does not match the captured request'
            self.records[active] = replace(record, state='completed', terminal_tick=tick)
            self.completed += 1
            completed_uid, self.active_uid = active, None
        elif inputs.from_valid:
            self.ignored_responses += 1
        if inputs.flush and active is not None:
            record = self.records[active]
            self.records[active] = replace(record, state='cancelled', terminal_tick=tick, reason=reason)
            self.cancelled += 1
            cancelled.append(active)
            self.active_uid = None
        fire_uid = accepted_uid = None
        if inputs.req_valid:
            record = self.records[offer_uid]
            assert record.state in ('offered', 'withdrawn'), 'request UID was reused after a physical fire'
            if before.req_ready:
                fire_uid = offer_uid
                self.req_fires += 1
                if inputs.flush:
                    self.flushed_on_accept += 1
                    self.records[offer_uid] = replace(record, state='flushed-on-fire', fire_tick=tick,
                        terminal_tick=tick, reason=reason)
                    cancelled.append(offer_uid)
                else:
                    assert self.active_uid is None, 'two live uncached fetch requests'
                    self.accepted += 1
                    accepted_uid = self.active_uid = offer_uid
                    self.records[offer_uid] = replace(record, state='accepted', fire_tick=tick)
            else:
                self.records[offer_uid] = replace(record, state='withdrawn')
        self.pulse_uid = completed_uid
        self.audit()
        return Events(offer_uid, fire_uid, accepted_uid, issued_uid, completed_uid,
                      tuple(cancelled), previous, response_uid)

    def reset(self, tick, reason):
        if self.active_uid is not None:
            uid = self.active_uid
            self.records[uid] = replace(self.records[uid], state='cancelled', terminal_tick=tick, reason=reason)
            self.cancelled += 1
        self.active_uid = self.pulse_uid = None
        self.epoch += 1
        self.audit()

    def audit(self):
        assert self.req_fires == self.accepted + self.flushed_on_accept, 'fire/effect ledger mismatch'
        assert self.accepted == self.completed + self.cancelled + int(self.active_uid is not None), 'lost request obligation'
        assert self.completed == sum(r.state == 'completed' for r in self.records.values()), 'duplicate completion count'
        assert self.cancelled == sum(r.state == 'cancelled' for r in self.records.values()), 'cancellation count mismatch'

    def snapshot(self, phase):
        self.audit()
        assert (phase == IDLE) == (self.active_uid is None), 'oracle phase and observed identity ledger diverged'
        return Status(phase, self.epoch, self.offered_cycles, self.req_fires, self.accepted,
            self.flushed_on_accept, self.issued, self.completed, self.cancelled,
            self.response_fires, self.ignored_responses, self.active_uid)
