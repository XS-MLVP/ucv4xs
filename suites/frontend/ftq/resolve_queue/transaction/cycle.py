"""Full simultaneous ResolveQueue input slot and input-owned report identity."""
from dataclasses import dataclass

from .types import ResolveReport


EMPTY_BACKEND = (None,) * 3


@dataclass(frozen=True, slots=True)
class ResolveInput:
    backend: tuple[ResolveReport | None, ...] = EMPTY_BACKEND
    ifu: ResolveReport | None = None
    ready: bool = False
    reset: bool = False
    redirect: tuple[int, int] | None = None  # flag, pointer value
    enqueue: int | None = None

    def __post_init__(self):
        backend = tuple(self.backend)
        if len(backend) != 3 or any(value is not None and type(value) is not ResolveReport for value in (*backend, self.ifu)):
            raise ValueError('ResolveQueue requires three backend lanes and one validated ResolveReport IFU lane')
        object.__setattr__(self, 'backend', backend)
        if type(self.ready) is not bool or type(self.reset) is not bool:
            raise ValueError('ResolveQueue ready/reset must be semantic bools')
        if self.redirect is not None:
            redirect = tuple(self.redirect)
            if (len(redirect) != 2 or any(type(value) is not int for value in redirect)
                    or redirect[0] not in (0, 1) or not 0 <= redirect[1] < 64):
                raise ValueError('ResolveQueue redirect must have exact flag/value identity')
            object.__setattr__(self, 'redirect', redirect)
        if self.enqueue is not None and (type(self.enqueue) is not int or not 0 <= self.enqueue < 64):
            raise ValueError('ResolveQueue enqueue pointer must be a six-bit integer')
        if self.reset and (any(backend) or self.ifu is not None or self.redirect is not None or self.enqueue is not None):
            raise ValueError('reset slot cannot carry unresolved semantic work')

    @property
    def reports(self):
        return (*self.backend, self.ifu)


@dataclass(frozen=True, slots=True)
class ReportAction:
    uid: tuple[int, int, int]  # epoch, input slot, source lane0..3
    report: ResolveReport
    tick: int


@dataclass(frozen=True, slots=True)
class ReportTerminal:
    action: ReportAction
    status: str
    tick: int
