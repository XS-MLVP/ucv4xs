"""Keep read identity and later-window identity distinct through the response."""
from suites.frontend.bpu.utage.model.semantic import (Context, indices, tag, index_view, tag_view,
    training_folds)
from suites.frontend.bpu.utage.checker.read_lifetime import Checks as VersionChecks,values
from suites.frontend.bpu.utage.model.ancestor_lifetime import PC,MATCH_PC,MATCH_HISTORY


class Checks(VersionChecks):
    def lifetime(self,read,response,effect):
        p=self.program
        source_context,later_context=Context.from_recent(p.history),Context.from_recent(MATCH_HISTORY)
        source_indices=indices(PC,source_context)
        self.check(True,source_indices!=indices(MATCH_PC,later_context),'two ancestors must be semantically distinguishable')
        same=p.relation=='read-with-write'
        self.check(True,read['tick']==effect['tick'] if same else read['tick']>effect['tick'],
            'actual owned read meets or strictly follows the original learning effect')
        self.check((True,PC,index_view(source_context),source_indices),
            (bool(read['events'].select),read['events'].read_pc,index_view(read['events'].read_context),read['read'].indices),
            'physical read belongs to original address/history, not later match context')
        self.check(True,response['frame'].read.entries is read['read'].entries,
            'later window consumes this exact old read tuple, not an equal younger query')
        self.check((MATCH_PC,tag_view(later_context),source_indices),
            (response['frame'].pc,tag_view(response['frame'].context),response['frame'].read.indices),
            'matching owns later address/history but retains original read indices')
        self.check(p.expected,values(response['actual']),'complete declared version under the correct two-ancestor combination')
        if response['actual'].hit:
            actual=response['actual'].meta
            self.check((source_indices,training_folds(later_context)),
                (tuple(actual['readIndex']),training_folds(
                    tuple(row['foldedHist'] for row in actual['foldedPathHistForTrain_hist']))),
                'complete defined public metadata retains both ancestors without synthesizing a same-context request')
        if same:
            entry=read['read'].entries[0]
            self.check((True,tag(PC,source_context,0),p.old_counter),(entry.valid,entry.tag,entry.counter),
                'same-boundary original entry precedes replacement or direction change')
        logical=tuple(sorted((table*512+index,old,new) for table,index,old,new,*_ in effect['effects'] if old!=new))
        self.check(p.changes(),logical,'independent original feedback learning effect')
        self.check(p.changes(),tuple(sorted(effect['native'].get('changes',()))),'actual full protection change at the declared boundary')
