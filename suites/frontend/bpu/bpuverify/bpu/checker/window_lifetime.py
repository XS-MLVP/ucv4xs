"""Only independently checked pipeline events enter source ownership."""
from bpuverify.bpu.checker.pipeline import PipelineChecker
from bpuverify.bpu.monitor.window_lifetime import AcceptedWindowEvents


class WindowPipelineChecker(PipelineChecker):
    def __init__(self, *, sources, capacity):
        super().__init__(sources=sources)
        self.windows = AcceptedWindowEvents(capacity)

    def capture(self, row, event):
        # The base checker verifies actual fires, flushes, PCs and all existing
        # predictor obligations before they can enter this separate ledger.
        redirect_owner = self.redirect_plans[0][0] if (
            not row['inputs']['reset'] and row['inputs']['redirect']['valid']
            and self.redirect_plans) else None
        super().capture(row, event)
        if self.failure is not None or self.last_tick != event.tick:
            return
        try:
            if row['inputs']['reset']:
                self.windows.reset()
                return
            if self.last_events.redirect is not None and redirect_owner is None:
                raise AssertionError('an external redirect needs its explicit original owner')
            self.windows.observe(self.last_cycle, event.tick, row['observed']['metadata'],
                redirect_owner=redirect_owner)
        except Exception as error:
            self.failure = error

    def receipt_window(self, source):
        return self.windows.receipt(self.source_token(source), source)
