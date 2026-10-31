"""UBTB query/reset scenarios; timing and signal access are not case data."""
from suites.frontend.bpu.models.query_reset_program import Program as QueryResetProgram,MODES,RULES


class Program(QueryResetProgram):
    def __init__(self,mode):
        super().__init__('ubtb',mode)
