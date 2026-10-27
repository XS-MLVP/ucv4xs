"""Earlier conditional execution bounds indirect selection and learning."""
from copy import deepcopy
from dataclasses import dataclass
from bpuverify.bpu.model.path_history import SHIFT, path_contribution
from bpuverify.tage.model.semantic import HISTORIES

PROFILES = tuple(entry + '.' + direction + '.' + mode
    for entry in ('compressed-entry', 'conditional-entry')
    for direction in ('weak-alternate', 'strong-provider') for mode in ('held', 'flowing'))

RULES = ('real-early-conditional-experience', 'stable-executed-path-context',
    'independent-retained-indirect-target', 'same-original-middle-decision',
    'earlier-condition-owns-final-target', 'no-spurious-strong-provider-repair',
    'executed-prefix-stops-at-condition', 'actual-indirect-learning-excluded',
    'actual-region-directory-preserved', 'actual-window-surrounds-feedback',
    'fresh-legally-executed-indirect-consumer', 'six-original-domains-immutable')

@dataclass(frozen=True)
class Layout:
    profile: str
    a: int = 0x40000103

    @property
    def b(self): return 0x40000001 if self.profile.startswith('compressed-entry.') else 0x40000002
    @property
    def d(self): return self.a + 0x100
    @property
    def c(self): return self.a + 0x200
    @property
    def flowing(self): return self.profile.endswith('.flowing')
    @property
    def strong(self): return '.strong-provider.' in self.profile
    @property
    def recovery_offset(self): return (self.a // 8) * 8 + 4 - self.a
    @property
    def recent(self):
        edge = (path_contribution((self.a // 8) * 8 + 4, self.b) << (2 * SHIFT)) ^ (
            path_contribution((self.b // 8) * 8 + 2, self.d) << SHIFT) ^ path_contribution(
                (self.d // 8) * 8 + 4, self.a)
        value = 0
        for bit in range(0, max(HISTORIES), 3 * SHIFT): value ^= edge << bit
        return value % (1 << max(HISTORIES))


def target_state(bank):
    model = bank.indirect
    return deepcopy(dict(memories=model.memories,
        caches=tuple(tuple((tuple(cache.slots), tuple(cache.older), cache.overwrites) for cache in banks)
            for banks in model.caches), regions=model.regions.regions,
        region_recency=tuple(model.regions._older), tick=model.tick, commits=model.commits,
        maintenance=tuple(model.maintenance), clear_start=model.clear_start))
