"""bpuverify.bpu.checker.sc.history components."""

from bpuverify.bpu.checker.sc.checker import ScChecker
from bpuverify.bpu.model.sc.training_path import training_indices
from bpuverify.bpu.model.sc.training_path import train_need_write
from bpuverify.bpu.model.sc.history import HistoryScReference


class HistoryScChecker(ScChecker):
    def __init__(self, case, **options):
        super().__init__(case, **options)
        self.reference = HistoryScReference()

    def check_training_path(self, row):
        super().check_training_path(row)
        t0, bits = row['t0'], row['training']['bits']
        common = bits['meta']['commonHR']
        if t0['fire'] and train_need_write(bits) and common['valid']:
            indices = training_indices(t0['inputs']['pc'], t0['folded_path'], common)
            debug = bits['meta']['sc']['debug']
            for table, field in (('globalTable_0', 'predGlobalIdx'), ('bwTable_0', 'predBWIdx')):
                self.check(debug[field][0], indices[table], table=table,
                    field='captured_common_history_index_matches_actual_train_hash')
