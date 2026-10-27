"""An original agreement holds protection while current confidence still learns."""
from bpuverify.utage.model.delayed_protection import Program as OriginalProgram, Step as OriginalStep
from bpuverify.utage.model.delayed_protection import MODES, ORDERS, RULES as ORIGINAL_RULES
from bpuverify.utage.model.usefulness_events import ProtectionState

RULES = (*ORIGINAL_RULES, 'late-agreement-preserves-nonzero-protection',
    'agreement-still-changes-current-direction', 'distinct-original-restores-after-agreement')


class Step(OriginalStep):
    __slots__ = ()
    @property
    def history(self): return 64 if self.phase in ('late-wrong', 'late-agreement') else 0
    @property
    def actual(self): return self.owner if self.phase in ('flip', 'late-agreement') else 1-self.owner


class Program(OriginalProgram):
    __slots__ = ()
    initial_roles = ('late-correct', 'late-restore', 'flip')
    after_flip_roles = ('late-wrong', 'late-agreement')
    rules = RULES

    @property
    def groups(self):
        phases = ('flip', 'late-correct', 'late-agreement', 'late-restore', 'late-wrong')
        recipe = [('allocate', (0, 1))]
        recipe.extend([(phase, (0, 1)) for phase in phases] if self.order == 'interleaved'
            else [(phase, (owner,)) for owner in (0, 1) for phase in phases])
        states = [None, None]; result = []; ordinal = 0
        for phase, owners in recipe:
            group = []
            for owner in owners:
                opposite = phase in self.after_flip_roles
                original = None if phase == 'allocate' else ProtectionState(
                    (3 if owner == 0 else 4) if opposite else (4 if owner == 0 else 3), 0 if opposite else 1)
                current = states[owner]
                actual = owner if phase in ('flip', 'late-agreement') else 1-owner
                base = 1-owner if phase == 'late-wrong' else owner
                after = ProtectionState(4 if owner == 0 else 3, 1) if phase == 'allocate' else current.feedback(
                    predicted=original.taken, base=base, actual=actual)
                step = Step(ordinal, owner, phase, original, current, after)
                states[owner] = after; group.append(step); ordinal += 1
            result.append(tuple(group))
        return tuple(result)

    def state(self): return dict(mode=self.mode, order=self.order, actual_feedbacks=12,
        initial=((4, 1), (3, 1)), final=((5, 1), (2, 1)), agreement_protection_before=1,
        original_agreement_is_not_current_direction=True, physical_enumeration=False,
        full_FTQ_source_eligibility_proved=False)


PROGRAMS = tuple(Program(mode, order) for mode in MODES for order in ORDERS)
