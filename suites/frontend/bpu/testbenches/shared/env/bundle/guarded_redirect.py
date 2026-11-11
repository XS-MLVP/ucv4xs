"""Reviewed raw GuardedPc redirect input, not a runtime width negotiation."""
from toffee.data import signal_width


def validate_guarded_cfi(leaf):
    if signal_width(leaf) != 50 or not leaf.IsInIO() or leaf.IsOutIO():
        raise ValueError('redirect CFI PC requires a 50-bit guarded halfword input')
