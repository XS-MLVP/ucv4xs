"""One outcome, separately qualified direction and correction experience."""
from suites.frontend.bpu.models.configuration import SC_TABLES, TAGE_TABLES

from dataclasses import dataclass
from suites.frontend.bpu.bpu.model.sc_loop_experience import Program as LoopProgram,PROFILES,RULES as LOOP_RULES
from suites.frontend.bpu.sc.model.threshold import ScThresholdModel
from suites.frontend.bpu.bpu.model.path_history import WIDTH,SHIFT
from suites.frontend.bpu.bpu.model.common_history import LOOKUP_WINDOW_CAPACITY,GHR_WIDTH
from suites.frontend.bpu.bpu.model.early_aging import require_recovery_window
from suites.frontend.bpu.tage.model.semantic import HISTORIES

RULES=LOOP_RULES+('joint-cold-teaches-both','SC-no-read-preserves-TAGE-learning',
    'joint-wrong-teaches-both','actual-TAGE-learning-offers')
CORE_LABELS=('used-cold','used-correct','used-wrong')


@dataclass(frozen=True,slots=True)
class Program(LoopProgram):
    @property
    def young_iteration(self):
        # Reserve the declared registered-read/observation window. Unlike
        # SC's saved indices, TAGE must still reread a live physical history.
        available=(WIDTH-max(HISTORIES))//SHIFT-LOOKUP_WINDOW_CAPACITY
        if available<=0:raise ValueError('no retained history budget for a younger joint consumer')
        return self.old_iteration+min(GHR_WIDTH+1,available)
    def require_feedback_window(self,current_edges,source_edges):
        return require_recovery_window(current_edges,source_edges,capacity=WIDTH,
            history_bits=max(HISTORIES),shift=SHIFT)
    @property
    def teaching_count(self):
        # SC must stay discriminating at the strongest TAGE confidence,
        # including after one real wrong outcome, not just at counter five.
        threshold=ScThresholdModel.for_default().initial[0]
        return next(n for n in range(1,32) if SC_TABLES*(2*(n-1)+1)>threshold//16)
    def state(self):
        return dict(LoopProgram.state(self),core_original_counters=(5,6,7),
            fresh_counters=(6,7,6),core_TAGE_and_SC_enabled=True,
            preparation_can_freeze_TAGE=True,retained_history_budget_bits=WIDTH-max(HISTORIES),
            actual_feedback_age_checked=True)


def tage_offer_values(writes,useful,actual):
    """Project every defined offer bit; never gate expected fields by DUT valid."""
    if len(actual)!=TAGE_TABLES:raise ValueError('all eight TAGE table offers must be observed')
    expected,observed={},{}
    for table,row in enumerate(actual):
        entries={way:(bank,value) for (t,bank,way),value in writes.items() if t==table}
        protection={way:(bank,value) for (t,bank,way),value in useful.items() if t==table}
        active=bool(entries or protection)
        e,a=dict(valid=active),dict(valid=bool(row['valid']))
        if active:
            banks={bank for bank,_ in (*entries.values(),*protection.values())}
            indices={v.row for _,v in (*entries.values(),*protection.values())}
            if len(banks)!=1 or len(indices)!=1:raise ValueError('one TAGE table offer needs one logical destination')
            bank,=banks;index,=indices
            e.update(index=index,bank=1<<bank,ways=sum(1<<w for w in entries.keys()|protection.keys()),
                entry_mask=tuple(w in entries for w in range(2)),useful_mask=tuple(w in protection for w in range(2)))
            a.update({k:tuple(map(bool,row[k])) if k.endswith('_mask') else row[k] for k in ('index','bank','ways','entry_mask','useful_mask')})
            for way,(_,value) in entries.items():
                e[f'entry{way}']=dict(valid=value.entry.valid,tag=value.entry.tag,counter=value.entry.counter,taken=value.taken)
                a[f'entry{way}']=dict(row['entries'][way],taken=bool(row['taken'][way]))
            for way,(_,value) in protection.items():
                e[f'useful{way}']=value.value;a[f'useful{way}']=row['useful'][way]
        expected[str(table)],observed[str(table)]=e,a
    return expected,observed
