"""suites.frontend.bpu.ras.monitor.decode components."""

from __future__ import annotations
from typing import Any
from suites.frontend.bpu.ras.transaction.types import RasState
from suites.frontend.bpu.ras.bundle.values import _plain


def _decode_state(sample: Any) -> RasState:
    return RasState(
        top=sample.top.as_int(),
        redirect_meta=_plain(sample.redirect_meta),
        commit_meta=_plain(sample.commit_meta),
    )
