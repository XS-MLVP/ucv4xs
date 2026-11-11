"""Central mapping from logical pin fields to generated RTL names.

Functional tests use this schema; only this module spells physical names.
"""


class Pins:
    """Logical field names; ``io`` adds the generated RTL prefix."""

    def io(self, suffix: str) -> str:
        return "io_" + suffix

    p_perf_0_value = "io_perf_0_value"


P = Pins()
