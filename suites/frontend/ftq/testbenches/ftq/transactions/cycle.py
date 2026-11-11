"""One explicit, immutable DefaultConfig producer/consumer input slot.

Staging a slot is a combinational preview, not acceptance. Each active edge
of a held Valid-only source is a distinct offer, including equal payloads.
"""
from dataclasses import dataclass

from suites.frontend.ftq.testbenches.ftq.env.bundle.abi import validate_metadata
from suites.frontend.ftq.testbenches.ftq.transactions.types import BackendRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import Consumers
from suites.frontend.ftq.testbenches.ftq.transactions.types import IfuRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import Meta
from suites.frontend.ftq.testbenches.ftq.transactions.types import Prediction
from suites.frontend.ftq.testbenches.ftq.transactions.types import PredictionSpec
from suites.frontend.ftq.testbenches.ftq.transactions.types import SoftPrefetch
from suites.frontend.ftq.testbenches.ftq.transactions.types import _identity
from suites.frontend.ftq.testbenches.ftq.model import CallRet
from suites.frontend.ftq.testbenches.resolve_queue.transactions.types import ResolveReport


@dataclass(frozen=True, slots=True)
class FtqInput:
    reset: bool = False
    prediction: Prediction | None = None
    meta: Meta | None = None
    backend_redirect: BackendRedirect | None = None
    ifu_redirect: IfuRedirect | None = None
    resolve: tuple[ResolveReport | None, ...] = (None,) * 3
    callret: tuple[CallRet | None, ...] = (None,) * 8
    soft_prefetch: tuple[SoftPrefetch | None, ...] = (None,) * 3
    commit: tuple[int, int] | None = None  # flag, value
    ahead: tuple[int, int] | None = None
    consumers: Consumers = Consumers()

    def __post_init__(self):
        if type(self.reset) is not bool or type(self.consumers) is not Consumers:
            raise ValueError('Ftq input requires semantic reset and validated Consumers')
        for name, kind in (('prediction', Prediction), ('meta', Meta),
                           ('backend_redirect', BackendRedirect), ('ifu_redirect', IfuRedirect)):
            value = getattr(self, name)
            if value is not None and type(value) is not kind:
                raise ValueError(f'Ftq {name} requires a validated {kind.__name__}')
        for name, count, kind in (('resolve', 3, ResolveReport), ('callret', 8, CallRet),
                                  ('soft_prefetch', 3, SoftPrefetch)):
            values = tuple(getattr(self, name))
            if len(values) != count or any(value is not None and type(value) is not kind for value in values):
                raise ValueError(f'Ftq {name} requires exactly {count} validated lanes')
            object.__setattr__(self, name, values)
        for name in ('commit', 'ahead'):
            value = getattr(self, name)
            if value is not None:
                if type(value) is not tuple or len(value) != 2:
                    raise ValueError(f'Ftq {name} requires a (flag, value) identity')
                _identity(value[1], value[0])
        if self.meta is not None:
            validate_metadata(self.meta.fields)
        if self.prediction is not None and self.prediction.s3_override and self.meta is not None:
            if (self.prediction.s3_flag, self.prediction.s3_ptr) != (self.meta.flag, self.meta.index):
                raise ValueError('Ftq s3 override and metadata must share one input-established pointer')


@dataclass(frozen=True, slots=True)
class InputReceipt:
    epoch: int
    slot: int
    frame: FtqInput
    tick: int


def allocation_plan(specs, *, consume=False, with_meta=True, meta_limit=None, start_index=0, start_flag=0):
    """Validate/freeze the WHOLE producer plan before changing readiness/time."""
    specs = tuple(specs)
    if any(type(spec) is not PredictionSpec for spec in specs):
        raise ValueError('Ftq allocation requires validated PredictionSpec entries')
    if type(consume) is not bool or type(with_meta) is not bool:
        raise ValueError('Ftq allocation consume/with_meta require semantic bools')
    if meta_limit is not None and (type(meta_limit) is not int or meta_limit < 0):
        raise ValueError('Ftq allocation meta_limit must be a nonnegative integer')
    _identity(start_index, start_flag)
    plan = []
    for index, spec in enumerate(specs):
        prediction = Prediction(spec.start_pc, taken=spec.taken, end_position=spec.end_position)
        absolute = start_index + index
        meta = (Meta(absolute % 64, flag=(start_flag + absolute // 64) & 1, fields=spec.meta)
                if with_meta and (meta_limit is None or index < meta_limit) else None)
        if meta is not None:
            validate_metadata(meta.fields)
        plan.append((prediction, meta))
    return tuple(plan)
