"""suites.frontend.bpu.testbenches.bpu.env.monitor.decode components."""

from __future__ import annotations
from typing import Any
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuMeta
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuPerf
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuPrediction
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuStage1Source
from suites.frontend.bpu.testbenches.bpu.env.bundle.values import _plain


def _require_fields(sample, fields):
    if set(sample) != fields:
        raise ValueError(f'BPU snapshot fields changed: expected {sorted(fields)}, got {sorted(sample)}')


def _decode_prediction(sample: Any, *, target_observable=False) -> BpuPrediction:
    _require_fields(sample, {'start_pc', 'taken', 'position', 's2_override', 's3_override'}
                    | ({'target'} if target_observable else set()))
    return BpuPrediction(
        start_pc=sample.start_pc.as_int(),
        target=sample.target.as_int() if target_observable else None,
        taken=sample.taken.as_int(),
        position=sample.position.as_int(),
        s2_override=sample.s2_override.as_int(),
        s3_override=sample.s3_override.as_int(),
    )


def _decode_meta(sample: Any, *, perf_observable=False) -> BpuMeta:
    _require_fields(sample, {'resolve', 'redirect'} | ({'perf'} if perf_observable else set()))
    perf = sample.perf if perf_observable else None
    return BpuMeta(
        resolve=_plain(sample.resolve),
        redirect=_plain(sample.redirect),
        perf=None if perf is None else BpuPerf(
            start_pc=perf.start_pc.as_int(),
            s1_target=perf.s1_target.as_int(),
            s1_taken=perf.s1_taken.as_int(),
            s1_position=perf.s1_position.as_int(),
            s1_source=BpuStage1Source(perf.s1_source.as_int()),
        ),
    )
