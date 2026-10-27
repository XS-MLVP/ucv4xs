"""MBTB query/reset scenarios; timing and signal access are not case data."""
from bpuverify.common.model.query_reset_program import Program as QueryResetProgram,MODES,RULES


class Program(QueryResetProgram):
    def __init__(self,mode):
        super().__init__('mbtb',mode)
