"""Original contribution survives a different branch taking the experience."""
from dataclasses import dataclass, replace
from bpuverify.utage.model.read_lifetime import LateReplacementProgram, REBUILD_PROFILES, REBUILD_RULES, MODES
from bpuverify.utage.model.usefulness_events import ProtectionState

QUALIFICATIONS = ('original-correct-opposition', 'original-correct-agreement', 'original-wrong')
RULES = REBUILD_RULES


@dataclass(frozen=True)
class Program(LateReplacementProgram):
    qualification: str

    def __post_init__(self):
        super().__post_init__()
        if self.qualification not in QUALIFICATIONS:
            raise ValueError('original correction, original agreement or original error required')

    @property
    def label(self): return '.'.join((self.profile, self.qualification, self.mode))
    @property
    def old_a(self):
        source = super().old_a
        return replace(source, base=int(source.counter >= 4) if self.qualification == QUALIFICATIONS[1] else source.base)
    @property
    def a_wrong(self): return self.qualification == QUALIFICATIONS[2]
    @property
    def failed_allocations(self): return int(self.a_wrong and self.mode == 'serial')

    @property
    def steps(self):
        original = super().steps
        rows = []
        # B becomes strongly confident without gaining extra protection:
        # these are correct agreements, not contributions against the base.
        for step in original[:-2]:
            if step.name.startswith('B-reward-'):
                step = replace(step, source=replace(step.source, base=step.actual),
                    before=ProtectionState(step.before.counter, 1), after=ProtectionState(step.after.counter, 1))
            rows.append(step)
        before = rows[-1].after
        actual = int(self.old_a.counter >= 4) ^ int(self.a_wrong)
        delta = -1 if self.a_wrong else 0 if self.qualification == QUALIFICATIONS[1] else 1
        after_a = ProtectionState(self.old_a.counter + (1 if actual else -1), before.useful + delta)
        rows.append(replace(original[-2], source=self.old_a, actual=actual, before=before,
            after=after_a, companion=self.a_wrong))
        b_actual = 1 - int(self.old_b.counter >= 4)
        rows.append(replace(original[-1], before=after_a,
            after=ProtectionState(self.old_b.counter + (1 if b_actual else -1), max(0, after_a.useful-1)),
            companion=not self.a_wrong or self.mode == 'adjacent',
            companion_useful_before=2 if self.a_wrong else 0))
        return tuple(rows)

    def consumers(self, *, after_a):
        a, b = self.steps[-2:]
        result = []
        for spec, expected in super().consumers(after_a=after_a):
            if spec.owner == 0:
                counter = a.after.counter
                short = (1, 0, counter, int(counter >= 4))
                long = (1, 1, counter, int(counter >= 4))
                absent = (0, None, None, None)
                if spec.history == 256: expected = short if after_a else absent
                elif after_a: expected = long if self.a_wrong else short
                else: expected = long if self.a_wrong and self.mode == 'serial' else absent
            elif spec.owner == 1 and not after_a:
                counter = (4 if b.actual else 3) if spec.history == 128 and b.companion else b.after.counter
                expected = (1, int(spec.history == 128 and b.companion), counter, int(counter >= 4))
            result.append((spec, expected))
        return tuple(result)

    def state(self):
        return dict(super().state(), qualification=self.qualification,
            strong_current_protection=1, expected_A_protection=self.steps[-2].after.useful,
            expected_final_protection=self.steps[-1].after.useful,
            failed_allocations=self.failed_allocations, original_algorithm_unchanged=True)


PROGRAMS = tuple(Program(profile, mode, qualification)
    for profile in REBUILD_PROFILES for qualification in QUALIFICATIONS for mode in MODES)
