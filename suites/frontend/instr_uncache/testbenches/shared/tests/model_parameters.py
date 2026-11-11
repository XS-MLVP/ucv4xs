"""Independent reference models for InstrUncache verification."""

from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import Inputs as ArbiterInputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import Outputs as ArbiterOutputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import arbiter_outputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import EntryModel
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import Inputs as EntryInputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import Outputs as EntryOutputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import IDLE
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import REFILL_REQ
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import REFILL_RESP
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import SEND_RESP
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import aligned_bus_address
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import cross_bus_boundary
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import cross_page_boundary
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import fetch_window
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import is_rvc
from suites.frontend.instr_uncache.testbenches.instr_uncache_entry.model import refill_needs_resend
from suites.frontend.instr_uncache.testbenches.instr_uncache.model import Inputs as TopInputs
from suites.frontend.instr_uncache.testbenches.instr_uncache.model import Outputs as TopOutputs
from suites.frontend.instr_uncache.testbenches.instr_uncache.model import TopModel

__all__ = [
    "ArbiterInputs", "ArbiterOutputs", "EntryInputs", "EntryModel", "EntryOutputs",
    "IDLE", "REFILL_REQ", "REFILL_RESP", "SEND_RESP", "TopInputs", "TopModel",
    "TopOutputs", "aligned_bus_address", "arbiter_outputs", "cross_bus_boundary",
    "cross_page_boundary", "fetch_window", "is_rvc", "refill_needs_resend",
]
