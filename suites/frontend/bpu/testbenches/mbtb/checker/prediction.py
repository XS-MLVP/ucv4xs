"""SDK association with mandatory input-established response/terminal checks."""
from toffee import Scoreboard
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbLookupDisposition
from suites.frontend.bpu.testbenches.mbtb.transactions.types import MbtbPrediction


class MbtbPredictionScoreboard(Scoreboard):
    def __init__(self,inputs,reference,*,compare):
        super().__init__('mbtb.prediction',compare=compare,expected=reference.response_expected)
        self.inputs=inputs
        self.reference=reference
        self.terminals=Scoreboard('mbtb.lookup-disposition')

    def check(self,*,expected,actual,context=None):
        # A semantic failure can stop further frame/UID bookkeeping. Preserve
        # that already-established error, rather than replacing it with the
        # consequent missing sample/delivery witness on the same SDK result.
        self.reference.raise_failure()
        if context is None or context.observed_event is None:
            raise ValueError('MainBTB result checking requires its actual SDK association context')
        uid,tick=context.sequence_id,context.observed_event.tick
        disposition=type(actual) is MbtbLookupDisposition
        wanted=self.inputs.delivery_expected(uid,tick,disposition=disposition)
        if disposition:
            # A scenario callback describes a functional response, not license
            # to waive or fabricate a different input's reset/filter terminal.
            self.terminals.check(expected=wanted,actual=actual.receipt(),context=context)
        else:
            self.inputs._check(True,type(actual) is MbtbPrediction,uid)
            # The independent model also checks this exact immutable SDK sample
            # when a user supplied a custom expected predicate. It adds checks;
            # it must not redefine a corrupted sample as a correct response.
            self.reference.response_expected(context.request,context)(actual)
            super().check(expected=expected,actual=actual,context=context)
        self.inputs.delivered(uid,tick)
