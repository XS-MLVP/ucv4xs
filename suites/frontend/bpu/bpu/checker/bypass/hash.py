"""Full frozen SRAM checks plus independently reconstructed PHR-to-index wiring."""
from collections import Counter
from suites.frontend.bpu.bpu.model.phr.model import fold
from suites.frontend.bpu.bpu.case.bypass.history_plan import read_indices

from suites.frontend.bpu.bpu.checker.bypass import sram as _v14


class SramChecker(_v14.SramChecker):
    def __init__(self):
        super().__init__()
        self.owner = None
        self.hash_checks = 0
        self.nonzero_hash_frames = 0

    def observe(self, phase, observation):
        row, event = observation.value, observation.event
        wanted_state = getattr(self.owner, 'current_phr_expected', None)
        if self.initialized and wanted_state is not None and not row['reset']:
            value = row['hash_inputs']
            if value['redirect_valid']:
                selected = [fold(value['redirect_low'], 6, 6), fold(value['redirect_low'], 12, 9)]
            else:
                stage = 'fold3' if value['s3_override'] else 'fold2' if value['s2_override'] else 'fold1'
                selected = [wanted_state[stage][i] for i in (2, 9)]
            self.check_sram(tuple(selected), value['normal_folds'], event, table=None,
                point='complete reset-derived PHR oldFoldedPhr priority and parent index-port wiring')
            self.check_sram(tuple(wanted_state['fold1'][i] for i in (1, 2, 7, 8)),
                value['s1_folds'], event, table=None, point='reset-derived four S1 tag folds wired to MicroTAGE')
            self.check_sram(read_indices(value['pc'], selected),
                tuple(table['inputs']['read_index'] for table in row['tables']), event, table=None,
                point='both real read indices independently derived from PC and full PHR reference')
            self.hash_checks += 3
            self.nonzero_hash_frames += int(any(selected))
        super().observe(phase, observation)

    def finish(self):
        result = super().finish()
        result.update(parent_hash_checks=self.hash_checks, nonzero_hash_frames=self.nonzero_hash_frames,
            full_parent_allocation_policy_modeled=False)
        return result
