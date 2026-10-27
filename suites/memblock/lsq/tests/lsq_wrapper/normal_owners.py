"""Normal StoreUnit CBO metadata, distinct from legacy interface-only actors.

Not yet wired into frozen/running mixed cases: their source must be captured
first. New normal callers must opt in explicitly; old stimuli are preserved.
"""
from dataclasses import dataclass, fields, replace

from .special_owners import SpecialStore


@dataclass(frozen=True)
class NormalCboStore(SpecialStore):
    def __post_init__(self):
        if self.cbo not in range(4) or self.memory or self.size != 4 or self.second_page is not None:
            raise ValueError("normal CBO is a cacheable single QB StoreUnit address package")
        if self.vaddr % 16 or self.paddr % 16:
            raise ValueError("normal CBO public PA/VA must already be aligned to16")

    @classmethod
    def from_interface(cls, owner):
        if owner.cbo not in range(4) or owner.memory or owner.second_page is not None:
            raise ValueError("cannot normalize non-CBO/uncache/cross-page owner into normal CBO")
        values = {field.name: getattr(owner, field.name) for field in fields(SpecialStore)}
        values.update(size=4, vaddr=owner.vaddr//16*16, paddr=owner.paddr//16*16)
        return cls(**values)

    def address(self, *, tail=False, miss=False):
        if tail:
            raise ValueError("normal CBO does not issue an unaligned tail")
        return replace(super().address(miss=miss), size=4, mask=65535, wline=True,
                       unaligned=False, cross_word=False, last=True)
