"""Coherent instruction confidence during concurrent experience handover."""
from dataclasses import dataclass,replace,asdict
from bpuverify.utage.model.displaced_branch import Program as SettledProgram,OWNERS,QUALIFICATIONS,MODES
from bpuverify.utage.model.dual_source import Experience,PC,EARLY,LATE

RULES=('normal-distinct-strengths','real-distinct-originals','original-before-installation',
    'normal-cold-installation','actual-handover-cadence','complete-instruction-counter-identity',
    'snapshot-qualified-write-mask','companion-still-learns','all-complete-native-versions',
    'all-protection-and-neighbors','fresh-three-instruction-consumers','immutable-originals')


@dataclass(frozen=True)
class Program(SettledProgram):
    rules=RULES
    @property
    def preparation_count(self):return 8
    @property
    def installation_ordinal(self):return 8

    @property
    def steps(self):
        baseline=SettledProgram.steps.fget(self)
        rows=list(baseline[:8])
        original=baseline[-1].sources
        install=baseline[8]
        rows.append(replace(install,taken=0,after=(Experience(self.replacement_position,3,1),install.before[1])))
        for number in range(2):
            before=rows[-1].after
            if self.replacement_position==EARLY:
                short=before[0].teach(original[0],0);writes=(0,1)
            elif self.mode=='adjacent' and number==0:
                # Its eligibility snapshot still owns instruction2/counter4.
                # The concurrent instruction7/counter3 is NOT its counter chain.
                own=rows[7].after[0]
                short=Experience(EARLY,own.counter-1,max(0,min(3,before[0].useful+(-1 if self.original_wrong else 1))))
                writes=(0,1)
            else:
                short=before[0];writes=(1,)
            long=before[1].teach(original[1],1)
            rows.append(replace(baseline[9+number],before=before,after=(short,long),writes=writes))
        return tuple(rows)

    def state(self):
        return dict(owner=self.owner,qualification=self.qualification,mode=self.mode,pc=PC,
            original_position=EARLY,replacement_position=self.replacement_position,
            original_state=[asdict(e) for e in self.steps[-1].sources],
            own_before_installation=asdict(self.steps[7].after[0]),
            installed=asdict(self.steps[8].after[0]),capture_after=self.capture_after,
            feedbacks=len(self.steps),physical_enumeration=False,full_FTQ_reachability_claimed=False)


PROGRAMS=tuple(Program(o,q,m) for o in OWNERS for q in QUALIFICATIONS for m in MODES)
OBLIGATIONS=tuple(p.label+'.'+rule for p in PROGRAMS for rule in RULES)
