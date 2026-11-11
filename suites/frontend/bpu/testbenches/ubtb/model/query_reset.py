"""UBTB query/reset scenarios; timing and signal access are not case data."""
from suites.frontend.bpu.testbenches.mbtb.model.query_reset_program import Program as QueryResetProgram
from suites.frontend.bpu.testbenches.mbtb.model.query_reset_program import MODES
from suites.frontend.bpu.testbenches.mbtb.model.query_reset_program import RULES


class Program(QueryResetProgram):
    def __init__(self,mode):
        super().__init__('ubtb',mode)
