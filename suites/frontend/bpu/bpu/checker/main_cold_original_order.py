"""Cold/current inputs differ in provenance, never in their retained owner rule."""
from copy import deepcopy
from suites.frontend.bpu.bpu.checker.main_original_order import Checks as OriginalChecks
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.model.main_original_order import EARLIER,LATER


class Checks(OriginalChecks):
    def start(self,sources):
        tokens=tuple(self.env.checker.source_token(source) for source in sources)
        for index,(source,token) in enumerate(zip(sources,tokens,strict=True)):
            entries=[(s.position,s.kind,s.counter) for row in source_entries(token.lookup) for s in row if s.hit]
            self.check([] if index==0 else [(EARLIER,3,2),(LATER,1,self.program.sibling_counter)],entries,
                'the old original is genuinely cold and the younger original owns the learned branch pair')
            self.env.checker.windows.ledger.live(self.env.checker.receipt_window(source))
        self.check(True,tokens[0].sequence<tokens[1].sequence,'cold and current are different live occurrence owners')
        return tokens,dict(cold_source=tokens[0].sequence,current_source=tokens[1].sequence,
            cold_original_literal_main=deepcopy(sources[0].meta.resolve['mbtb_entries']),
            actual_original_qualifications_live_before_send=True,
            no_redirect_ever_discarded_cold=not any(tokens[0].sequence in r['discarded']
                for r in self.env.checker.windows.redirects))
