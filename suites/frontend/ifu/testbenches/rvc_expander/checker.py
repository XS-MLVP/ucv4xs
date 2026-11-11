"""ISA-based comparison with qualifiers from the oracle, never from the DUT."""
from toffee import Scoreboard

from suites.frontend.ifu.testbenches.rvc_expander.model.rvc import Expansion
from suites.frontend.ifu.testbenches.rvc_expander.model.rvc import expand

from suites.frontend.ifu.testbenches.rvc_expander.transactions import Decoded


def check_decoding(request, observed, expected=None):
    if not isinstance(observed, Decoded):
        raise TypeError('RvcExpander requires a complete Decoded snapshot')
    oracle = expand(request.word, fs_is_off=bool(request.fs_is_off))
    if expected is not None and not isinstance(expected, Expansion):
        raise TypeError('RvcExpander expected value must be an Expansion')
    wanted = oracle if expected is None else expected
    if (not isinstance(wanted.ill, int) or wanted.ill not in (0, 1)
            or not isinstance(wanted.hint, int) or wanted.hint not in (0, 1)
            or not isinstance(wanted.bits, int) or not 0 <= wanted.bits < (1 << 32)):
        raise ValueError('RvcExpander expected fields are outside the architectural encoding domain')
    Scoreboard('ifu.rvc_expander.ill').check(expected=bool(wanted.ill), actual=observed.ill)
    # Hint canonicalisation and illegal payload bits are unspecified by the
    # architectural contract. An expected override cannot widen these masks.
    if not oracle.ill and not oracle.hint:
        Scoreboard('ifu.rvc_expander.bits').check(expected=wanted.bits, actual=observed.bits)
