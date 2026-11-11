"""Independent validity-qualified comparisons and explicit zero reset answers."""
from dataclasses import asdict

from toffee import Scoreboard

from suites.frontend.ifu.testbenches.uncache_unit.model.uncache import Outputs


RESET = Outputs(1, 0, 0, 0, 0, 0, 0, 1, 0)


def check_outputs(observed, oracle, *, phase, expected=None):
    if not isinstance(observed, Outputs) or not isinstance(oracle, Outputs):
        raise TypeError('Uncache requires complete semantic Outputs snapshots')
    if expected is not None and not isinstance(expected, Outputs):
        raise TypeError('Uncache expected override must be an Outputs snapshot')
    wanted = oracle if expected is None else expected
    fields = ['req_ready', 'resp_valid', 'to_valid']
    if oracle.to_valid:
        fields += ['to_paddr', 'to_mem_back_mm', 'to_mem_page_nc']
    if oracle.resp_valid:
        fields += ['resp_data', 'resp_exception', 'resp_need_resend']
    Scoreboard(f'ifu.uncache_unit.{phase}').check(
        expected={field: getattr(wanted, field) for field in fields},
        actual={field: getattr(observed, field) for field in fields})


def check_reset(observed):
    if not isinstance(observed, Outputs):
        raise TypeError('Uncache reset requires a complete Outputs snapshot')
    Scoreboard('ifu.uncache_unit.reset').check(expected=asdict(RESET), actual=asdict(observed))
