"""ABTB training/cleanup -> shadow buffers -> SRAM writes, from reset only.

The bank read request is an input to this layer, not a drain-ready oracle.
The integrated replay derives that request from PC/history/stage control.
SRAM reset takes 64 non-reset cycles; no observed write response seeds state.
Prediction entries/hits are inputs, so full prediction/SRAM-read correctness
is deliberately not claimed by this write-lineage reference.
"""
from copy import deepcopy

from bpuverify.abtb.model.state.counter import CounterReference
from bpuverify.abtb.model.state.counter import victim
from bpuverify.abtb.model.state.writebuffer import WriteBufferReference
from bpuverify.abtb.model.state.writebuffer import zero

INDIRECT = 3  # Bundles.scala: BranchType.Direct=2, Indirect=3.


def training_requests(transaction, counter):
    """T1 combinational decisions, including the registered victim choice."""
    requests, roles = [None] * 4, [None] * 4
    if transaction is None:
        return requests, roles
    tx, meta = transaction, transaction['meta']
    attribute = dict(branchType=tx['branch_type'], rasAction=tx['ras_action'])
    matching = [way for way, entry in enumerate(meta['entries'])
        if entry['hit'] and entry['position'] == tx['position']
        and entry['attribute'] == attribute]
    allocate = not matching and bool(tx['taken'])
    correct = bool(matching and tx['branch_type'] == INDIRECT
        and meta['entries'][matching[0]]['targetLowerBits'] != tx['target'] & ((1 << 22) - 1))
    if not (allocate or correct):
        return requests, roles
    for bank in range(4):
        if not meta['bankMask'] & (1 << bank):
            continue
        requests[bank] = dict(need_reset=int(allocate), set_index=meta['setIdx'],
            way=victim(counter.plru[bank][meta['setIdx']]) if allocate else matching[0],
            valid=1, tag=tx['pc'] & ((1 << 24) - 1), position=tx['position'],
            branch_type=tx['branch_type'], ras_action=tx['ras_action'],
            target_low=tx['target'] & ((1 << 22) - 1))
        roles[bank] = 'allocate' if allocate else 'correct_target'
    return requests, roles


def cleanup_request(meta, *, fire):
    """Last matching (i,j) wins, exactly as ABTB Helpers.detectMultiHit."""
    selected = None
    if fire:
        entries = meta['entries']
        for first in range(4):
            for second in range(first + 1, 4):
                if entries[first]['hit'] and entries[second]['hit']\
                        and entries[first]['position'] == entries[second]['position']:
                    selected = first
    return None if selected is None else dict(set_index=meta['setIdx'],
        bank_mask=meta['bankMask'], way=selected)


class WriteLineageReference:
    def __init__(self):
        self.initialized = False
        self.reset()

    def reset(self):
        self.counter = CounterReference()
        self.buffers = [WriteBufferReference() for _ in range(4)]
        self.request2, self.role2 = [None] * 4, [None] * 4
        self.cleanup = None
        self.reset_remaining = 64
        # None means not yet reset by the SRAM reset walker, not a zero guess.
        self.sram = [[[None for _ in range(4)] for _ in range(64)] for _ in range(4)]

    def current_requests(self):
        requests, roles = deepcopy(self.request2), self.role2[:]
        if self.cleanup is not None:
            for bank in range(4):
                if requests[bank] is None and self.cleanup['bank_mask'] & (1 << bank):
                    payload = zero()
                    payload.update(need_reset=1, set_index=self.cleanup['set_index'], way=self.cleanup['way'])
                    requests[bank], roles[bank] = payload, 'clean_multi_hit'
        return requests, roles

    def advance(self, *, reset, accepted, read_pressure, new_cleanup=None):
        if len(read_pressure) != 4:
            raise ValueError('exactly four bank read-pressure inputs required')
        if reset:
            self.reset()
            self.initialized = True
            return dict(requests=[None] * 4, roles=[None] * 4, drains=[], actions=[],
                writes=[], transitions=[], ready=[False] * 4, cleanup_applied=False,
                sram_reset_row=None)
        if not self.initialized:
            raise ValueError('write lineage must start at an actual reset')
        next_requests, next_roles = training_requests(self.counter.pending1, self.counter)
        requests, roles = self.current_requests()
        ready = [not self.reset_remaining and not read_pressure[bank] for bank in range(4)]
        writes, drains, actions = [], [], []
        for bank, buffer in enumerate(self.buffers):
            drain, action = buffer.advance(reset=0, write=requests[bank], ready=ready[bank])
            if drain is not None:
                payload = drain['payload']
                self.sram[bank][payload['set_index']][payload['way']] = deepcopy(payload)
                writes.append(dict(bank=bank, set_index=payload['set_index'], way=payload['way'],
                    reset_counter=payload['need_reset']))
                drains.append(dict(bank=bank, **drain))
            if action is not None:
                actions.append(dict(bank=bank, request_role=roles[bank], **action))
        reset_row = None
        if self.reset_remaining:
            reset_row = 64 - self.reset_remaining
            for bank in range(4):
                self.sram[bank][reset_row] = [zero() for _ in range(4)]
            self.reset_remaining -= 1
        transitions = self.counter.advance(reset=0, accepted=accepted, writes=writes)
        applied = any(role == 'clean_multi_hit' for role in roles)
        # New S2 cleanup wins over clearing an old applied request. There is a
        # single pending-valid register, not a per-bank retry queue.
        if new_cleanup is not None:
            self.cleanup = deepcopy(new_cleanup)
        elif applied:
            self.cleanup = None
        self.request2, self.role2 = next_requests, next_roles
        return deepcopy(dict(requests=requests, roles=roles, drains=drains, actions=actions,
            writes=writes, transitions=transitions, ready=ready,
            cleanup_applied=applied, sram_reset_row=reset_row))
