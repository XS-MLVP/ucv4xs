"""Check real SRAM requests, defined responses and shadow/array selection."""
from dataclasses import asdict
from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from suites.frontend.bpu.bpu.checker.bypass.checker import BypassChecker
from suites.frontend.bpu.bpu.model.bypass.sram import SramReference
from suites.frontend.bpu.bpu.model.bypass.sram import zero_data


class SramChecker(BypassChecker):
    def __init__(self):
        super().__init__()
        self.srams = [SramReference() for _ in range(2)]
        self.sram_scoreboard = Scoreboard('bpu.integrated_microtage_sram')
        self.sram_cycles = []
        self.defined_responses = 0

    def check_sram(self, expected, actual, event, *, table, point):
        self.sram_scoreboard.check(expected=expected, actual=actual,
            context=CheckContext(scoreboard=self.sram_scoreboard.name, mode=ScoreboardMode.DIRECT,
                request=dict(table=table, point=point), observed_event=event))

    def observe(self, phase, observation):
        row, event = observation.value, observation.event
        for table, reference in enumerate(self.srams):
            actual, shadow = row['sram'][table], row['tables'][table]
            inputs = shadow['inputs']
            output = self.references[table].outputs(inputs)
            write = output['write']
            if self.initialized:
                def check(expected, actual, point):
                    self.check_sram(expected, actual, event, table=table, point=point)
                check(inputs['read_index'], actual['read_index'], 'parent read index equals shadow boundary')
                check(reference.reset_done, actual['reset_done'], 'independently counted128cycle SRAM reset')
                check(0 if reference.read_bank is None else 1 << reference.read_bank,
                    actual['bank_mask'], 'registered bank selection')
                check(int(reference.conflict), actual['conflict'], 'independently derived forced-read conflict')
                if reference.write_bank is not None:
                    check(1 << reference.write_bank, actual['write_mask'], 'registered shadow-write bank')
                controls = reference.controls(inputs['read_index'], write)
                for bank, (expected, observed) in enumerate(zip(controls, actual['banks'], strict=True)):
                    check(expected, {key: observed[key] for key in expected}, f'bank{bank} full requests/reset/array control')
                    wanted = reference.bank_response(bank)
                    if wanted is not None:
                        check(wanted, observed['response'], f'bank{bank} defined RAM response from reset+writes')
                wanted = reference.response(output['response'])
                if wanted is not None:
                    check(wanted, {key: actual['response'][key] for key in wanted},
                        'full defined table response or forced-conflict invalid bit')
                    self.defined_responses += 1
            if phase == 'preedge':
                witness = reference.advance(inputs['read_index'], write, reset=bool(row['reset']))
                self.sram_cycles.append(dict(table=table, tick=event.tick, **witness))
        super().observe(phase, observation)

    def finish(self):
        result = super().finish()
        result.update(SRAM_state_derived_from_reset_and_predicted_shadow_writes=True,
            SRAM_requests_and_defined_responses_checked=True,
            actual_raw_memory_cells_sampled=False, parent_training_policy_modeled=False,
            defined_table_responses=self.defined_responses, SRAM_checks=asdict(self.sram_scoreboard.status),
            SRAM_cycles=self.sram_cycles)
        return result
