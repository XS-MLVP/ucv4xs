"""Independent full-width Sdtrig oracle; no DUT-derived validity mask."""
from toffee import Scoreboard

from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import ACTION_BREAKPOINT
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import ACTION_DEBUG
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import EQ
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import GE
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import LT
from suites.frontend.ifu.testbenches.frontend_trigger.model.trigger import TRIGGERS

from suites.frontend.ifu.testbenches.frontend_trigger.transactions import Actions


def check_actions(observed, expected, *, phase):
    if not isinstance(observed, Actions):
        raise TypeError('FrontendTrigger requires a complete Actions snapshot')
    expected = Actions(expected).actions
    Scoreboard(f'ifu.frontend_trigger.{phase}').check(expected=expected, actual=observed.actions)


def require_csr_table(triggers):
    """Validate provenance separately from the wider, explicitly named port domain."""
    if len(triggers) != TRIGGERS:
        raise ValueError('CSR trigger table must have four entries')
    for index, trigger in enumerate(triggers):
        if trigger.match_type not in (EQ, GE, LT) or trigger.select != 0:
            raise ValueError('CSR producer permits only EQ/GE/LT and select=0')
        if trigger.action not in (ACTION_BREAKPOINT, ACTION_DEBUG):
            raise ValueError('CSR producer permits only breakpoint/debug actions')
        # CSR's complete-vector check forbids adjacent chain bits, but it does
        # NOT force the last slot's chain bit to0. Preserve that reachable case.
        if trigger.chain and index and triggers[index - 1].chain:
            raise ValueError('CSR producer forbids adjacent chain bits')
