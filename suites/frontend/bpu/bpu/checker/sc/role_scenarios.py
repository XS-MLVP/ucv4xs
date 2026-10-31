"""suites.frontend.bpu.bpu.checker.sc.role_scenarios components."""

from suites.frontend.bpu.bpu.checker.phr.checking import BpuPhrChecker
from suites.frontend.bpu.bpu.model.phr.model import path_hash


class ZeroHistoryChecker(BpuPhrChecker):
    def observe(self, observation):
        super().observe(observation)
        if len(self.records) < 2:
            return
        row = observation.value
        self.check([0] * 52, row['state']['cells'], field='all52_physical_history_cells_remain_zero')
        for name in ('fold0_reg', 'fold1', 'fold2', 'fold3'):
            self.check([0] * 19, row['state'][name], field='all76_fold_registers_remain_zero', bank=name)
        self.check(0, self.reference.logical(), field='independently_reconstructed_full_history_remains_zero')
        for name in ('s1', 's2', 's3'):
            branch = row['boundary'][name]
            if branch['valid'] and branch['prediction']['taken']:
                prediction = branch['prediction']
                self.check(0, path_hash((branch['start_pc'] & ~7) + prediction['position'],
                    prediction['target']), field='every_actual_taken_prediction_has_zero_path_hash', stage=name)
        if row['boundary']['redirect']['valid']:
            self.check(0, row['boundary']['redirect']['taken'], field='real_not_taken_checkpoint_recovery')


class CombinedChecks:
    def __init__(self, sc, phr):
        self.sc, self.phr = sc, phr

    def __getattr__(self, name):
        return getattr(self.sc, name)

    def raise_failure(self):
        self.sc.raise_failure()
        self.phr.raise_failure()
