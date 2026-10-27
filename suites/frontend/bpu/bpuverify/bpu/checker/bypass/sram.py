"""Independently check raw conflict-valid and retain actual SRAM witnesses."""
from copy import deepcopy
from bpuverify.bpu.checker.bypass import sram_reset as _v6


class SramChecker(_v6.SramChecker):
    def __init__(self):
        super().__init__()
        self.bank_writes, self.SRAM_reads, self.forced_conflicts = [], [], []

    def observe(self, phase, observation):
        row, event = observation.value, observation.event
        if self.initialized:
            for table, reference in enumerate(self.srams):
                actual = row['sram'][table]
                inputs = row['tables'][table]['inputs']
                output = self.references[table].outputs(inputs)
                raw = reference.response(dict(hit=0))
                if raw is not None:
                    self.check_sram(raw['data_valid'], actual['raw_entry_valid'], event,
                        table=table, point='raw SRAM valid independently includes forced conflict even on shadow hit')
                if phase == 'preedge' and not row['reset']:
                    for bank, request in enumerate(reference.controls(inputs['read_index'], output['write'])):
                        if request['write_valid']:
                            self.bank_writes.append(dict(tick=event.tick, table=table, bank=bank,
                                index=output['write']['index'], read_index=inputs['read_index'],
                                force=output['write']['force'], data=deepcopy(request['write_data'])))
                    if reference.conflict and reference.write_bank == reference.read_bank:
                        self.forced_conflicts.append(dict(tick=event.tick, table=table,
                            bank=reference.read_bank, expected_raw_valid=0,
                            actual_raw_valid=actual['raw_entry_valid']))
                    wanted = reference.response(output['response'])
                    if (not output['response']['hit'] and wanted is not None
                            and len(wanted) == 4 and wanted['data_valid']):
                        self.SRAM_reads.append(dict(tick=event.tick, table=table,
                            index=reference.read_addresses[reference.read_bank],
                            data=deepcopy(wanted), actual=deepcopy(actual['response']),
                            no_shadow_hit=True))
        super().observe(phase, observation)

    def finish(self):
        result = super().finish()
        result.update(raw_SRAM_conflict_valid_independently_compared=True,
            bank_writes=self.bank_writes, SRAM_reads=self.SRAM_reads,
            forced_conflicts=self.forced_conflicts)
        return result
