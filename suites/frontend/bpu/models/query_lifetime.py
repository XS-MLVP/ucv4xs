"""One response obligation, associated by immutable source identity, not PC."""


class QueryLease:
    def __init__(self):
        self.snapshot = self.accepted_tick = self.response_tick = self.reset_tick = None
        self.disposition = None

    def accept(self, snapshot, tick):
        if snapshot is None or self.snapshot is not None or self.reset_tick is not None:
            raise AssertionError('one real pre-reset query snapshot is required')
        self.snapshot, self.accepted_tick = snapshot, tick

    def response(self, snapshot, tick):
        if self.reset_tick is not None:
            raise AssertionError('old response cannot enter a new reset epoch')
        if self.snapshot is None or snapshot is not self.snapshot:
            return False
        if self.response_tick is not None or tick < self.accepted_tick:
            raise AssertionError('duplicate or younger-than-request response')
        self.response_tick, self.disposition = tick, 'responded'
        return True

    def reset(self, tick):
        if self.snapshot is None or self.reset_tick is not None or tick <= self.accepted_tick:
            raise AssertionError('effective reset must follow one actual old request')
        self.reset_tick = tick
        if self.response_tick is None:
            self.disposition = 'reset-ended'

    def state(self):
        return dict(accepted_tick=self.accepted_tick, response_tick=self.response_tick,
                    reset_tick=self.reset_tick, disposition=self.disposition)
