"""Public environment for LoadUnitS4 (pure identity pass-through).

The canonical payload schema and observation types live with the transaction
layer; this module exposes the environment entry point used by the tests.
"""
from __future__ import annotations

from suites.memblock.lsu.testbenches.load_s4.transactions import PAYLOAD_FIELDS
from suites.memblock.lsu.testbenches.load_s4.transactions import S4HeadPayload
from suites.memblock.lsu.testbenches.load_s4.transactions import S4Observation
from suites.memblock.lsu.testbenches.load_s4.env.passthrough import LoadS4Env

FIELDS = PAYLOAD_FIELDS

__all__ = ["FIELDS", "LoadS4Env", "PAYLOAD_FIELDS", "S4HeadPayload", "S4Observation"]
