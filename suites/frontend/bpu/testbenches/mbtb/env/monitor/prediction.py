"""SDK cycle sampling with an input-established, non-wire metadata ancestor."""
from suites.frontend.bpu.testbenches.shared.env.monitor.cycle import CycleMonitor
from suites.frontend.bpu.testbenches.mbtb.env.monitor.decode import _decode
from suites.frontend.bpu.testbenches.mbtb.transactions.metadata import freeze_metadata
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbPrediction
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbLookupDisposition


class MbtbPredictionMonitor(CycleMonitor):
    def __init__(self,binding,inputs):
        super().__init__(binding,decoder=_decode)
        self.inputs=inputs

    def _capture(self,event):
        actual=super()._capture(event)
        terminal=self.inputs.disposition_at(event.tick)
        if terminal is not None:
            return MbtbLookupDisposition(terminal.uid,terminal.state,terminal.offer_epoch,
                terminal.offer_tick,terminal.terminal_tick,event.tick,actual)
        origin=self.inputs.source_at(event.tick)
        if origin is None:return actual
        frozen=freeze_metadata(actual.meta_entries,prediction=True,origin=origin)
        self.inputs.register_source(origin,frozen)
        return MbtbPrediction(actual.entries,frozen)
