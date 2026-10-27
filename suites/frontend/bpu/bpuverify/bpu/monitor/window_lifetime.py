"""Bind the independent eligibility ledger to already-compared BPU events.

This observes *all* S1 admissions, not just receipts selected by a testcase.
It does not drive FTQ pointers, infer backend commit, or prove architectural
reachability. Published metadata below is explicitly a checked projection.
"""
from collections import Counter

from bpuverify.bpu.model.window_lifetime import WindowLifetimes


class AcceptedWindowEvents:
    def __init__(self, capacity):
        self.ledger = WindowLifetimes(capacity)
        self.counts = Counter()
        self.reset()

    def reset(self):
        self.ledger.reset()
        self.windows, self.accepted_at, self.published_at = {}, {}, {}
        self.peak = 0
        self.redirects = []

    def owner(self, token):
        if token is None or token.sequence not in self.windows:
            raise AssertionError('correction/metadata lacks its previously accepted S1 occurrence')
        original = self.windows[token.sequence]
        if original.pc != token.pc:
            raise AssertionError('one accepted occurrence changed its original PC')
        return original

    def observe(self, cycle, tick, metadata, *, redirect_owner=None):
        if redirect_owner is not None:
            self._redirect(redirect_owner, tick, 'external')
            return
        if cycle.final_repair:
            self._redirect(cycle.tokens[2], tick, 'S3')
        elif cycle.middle_repair:
            self._redirect(cycle.tokens[1], tick, 'S2')
        if cycle.fires[1] and not cycle.flushes[0]:
            token = cycle.tokens[0]
            if token is None or token.sequence in self.windows:
                raise AssertionError('S1 acceptance needs one fresh original occurrence')
            self.windows[token.sequence] = self.ledger.admit(token.pc)
            self.accepted_at[token.sequence] = tick
            self.counts['S1-admission'] += 1
            self.peak = max(self.peak, len(self.ledger.active))
        if cycle.metadata is not None:
            token = cycle.metadata
            if metadata['pc'] != token.pc or not metadata['valid']:
                raise AssertionError('metadata does not belong to this exact S3 occurrence')
            self.ledger.publish_metadata(self.owner(token), {
                'history': metadata['history'], 'main': metadata['main']})
            self.published_at[token.sequence] = tick
            self.counts['S3-metadata'] += 1

    def _redirect(self, token, tick, kind):
        original = self.owner(token)
        dropped = self.ledger.redirect(original)
        self.redirects.append(dict(tick=tick, kind=kind, owner=token.sequence,
            discarded=tuple(sequence for sequence, source in self.windows.items()
                if any(source is old for old in dropped))))
        self.counts[kind + '-correction'] += 1

    def receipt(self, token, source):
        original = self.owner(token)
        if (self.accepted_at[token.sequence], self.published_at.get(token.sequence), original.pc) != (
                source.prediction_tick, source.meta_tick, source.prediction.start_pc):
            raise AssertionError('selected receipt does not retain its actual original boundaries')
        return original


