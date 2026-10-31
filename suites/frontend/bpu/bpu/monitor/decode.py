"""suites.frontend.bpu.bpu.monitor.decode components."""

from __future__ import annotations
from typing import Any
from suites.frontend.bpu.bpu.transaction.types import BpuMeta
from suites.frontend.bpu.bpu.transaction.types import BpuPerf
from suites.frontend.bpu.bpu.transaction.types import BpuPrediction
from suites.frontend.bpu.bpu.transaction.types import BpuStage1Source
from suites.frontend.bpu.bpu.bundle.values import _plain


def _decode_prediction(sample: Any) -> BpuPrediction:
    return BpuPrediction(
        start_pc=sample.start_pc.as_int(),
        target=sample.target.as_int(),
        taken=sample.taken.as_int(),
        position=sample.position.as_int(),
        s2_override=sample.s2_override.as_int(),
        s3_override=sample.s3_override.as_int(),
    )


def _decode_meta(sample: Any) -> BpuMeta:
    perf = sample.perf
    return BpuMeta(
        resolve=_plain(sample.resolve),
        redirect=_plain(sample.redirect),
        perf=BpuPerf(
            start_pc=perf.start_pc.as_int(),
            s1_target=perf.s1_target.as_int(),
            s1_taken=perf.s1_taken.as_int(),
            s1_position=perf.s1_position.as_int(),
            s1_source=BpuStage1Source(perf.s1_source.as_int()),
        ),
    )
