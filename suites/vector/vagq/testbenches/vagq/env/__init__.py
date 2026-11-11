"""Small explicit environment composing driver, model, checker and coverage."""
from dataclasses import dataclass, field

from suites.vector.vagq.testbenches.vagq.checker import Checker
from suites.vector.vagq.testbenches.vagq.coverage import Coverage
from suites.vector.vagq.testbenches.vagq.env.driver import Driver
from suites.vector.vagq.testbenches.vagq.model import IntegrationModel
from suites.vector.vagq.testbenches.vagq.env.probe import bind
from suites.vector.vagq.testbenches.vagq.env.probe import decode
from suites.vector.vagq.testbenches.vagq.transactions import AddrPacket
from suites.vector.vagq.testbenches.vagq.transactions import AdmissionStatus
from suites.vector.vagq.testbenches.vagq.transactions import Beat
from suites.vector.vagq.testbenches.vagq.transactions import DataPacket


@dataclass
class Env:
    dut: object
    ports: object
    sample: object
    driver: Driver
    model: IntegrationModel
    checker: Checker
    coverage: Coverage
    check_enabled: bool = True
    _sample_cycle: int = 0
    _writebacks: dict = field(default_factory=dict)

    @classmethod
    def create(cls, dut):
        ports, sample = bind(dut)
        return cls(dut, ports, sample, Driver(dut, ports),
                   IntegrationModel(), Checker(), Coverage())

    def reset(self):
        self.driver.reset_dut()
        self.model = IntegrationModel()
        self.coverage.reset()
        # Sample identity restarts at zero after the reset sequence; every
        # observation produced by cycle()/present() increments exactly once.
        self._sample_cycle = 0
        self._writebacks = {}

    def _observe(self, raw, beat):
        cycle = getattr(self, '_sample_cycle', 0)
        observation = decode(raw, cycle=cycle, beat=beat)
        self._sample_cycle = cycle + 1
        writeback = observation.writeback
        if writeback.valid:
            plan = self.model.plans.get(writeback.entry_idx)
            if plan is not None and not plan.flushed:
                self._check_writeback_identity(plan, writeback)
                if not hasattr(self, '_writebacks'):
                    self._writebacks = {}
                self._writebacks.setdefault(
                    writeback.entry_idx, []).append((plan, writeback))
        return observation

    @staticmethod
    def _check_writeback_identity(plan, writeback):
        """Require the public writeback to belong to the admitted attempt.

        Entry lookup alone is not identity: an entry index can be reused and
        a wrong ROB age/flags or a different micro-op must never be credited
        to the live plan.  The compared fields are the public attempt
        identity used by the existing model/sequence contract: entry index,
        ROB flag/value and uop index.
        """
        expected = plan.addr
        mismatches = [
            f'{name}: admitted={wanted}, writeback={actual}'
            for name, wanted, actual in (
                ('entry_idx', expected.entry_idx, writeback.entry_idx),
                ('rob_flag', expected.rob_flag, writeback.rob_flag),
                ('rob_value', expected.rob_value, writeback.rob_value),
                ('uop_idx', expected.uop_idx, writeback.uop_idx),
            )
            if wanted != actual
        ]
        if mismatches:
            raise AssertionError(
                f'writeback identity does not belong to the admitted attempt '
                f'for entry {expected.entry_idx}: ' + '; '.join(mismatches))

    def admit(self, addr: AddrPacket, data: DataPacket):
        """Declare one address/data admission on the external interface."""
        self.model.admit(addr, data)

    def observation_only(self):
        """Stop the integration checker for an independent-oracle audit probe.

        The ISA audit files compare against ``isa_reference`` instead of this
        integration model.  This is not a silent pass: every audited request
        still enters the caller's independent ledger.
        """
        self.check_enabled = False

    def cycle(self, beat: Beat, *, admit=None, check=None):
        self.driver.drive(beat)
        raw = self.sample()
        if admit is not None:
            if isinstance(admit, list):
                for addr, data in admit:
                    self.admit(addr, data)
            else:
                self.admit(*admit)
        if (self.check_enabled if check is None else check):
            self.checker.compare(self.model, raw, beat)
        self.coverage.sample(beat, raw, self.model)
        observation = self._observe(raw, beat)
        self.driver.tick()
        return observation

    def present(self, beat: Beat):
        """Present one public beat and return its immutable observation.

        This is the transaction-level entry point for external audit probes
        that carry their own response ledger.  It advances exactly one DUT
        clock and never acknowledges a request on the caller's behalf.
        """
        self.driver.drive(beat)
        raw = self.sample()
        observation = self._observe(raw, beat)
        self.driver.tick()
        return observation

    def admission_status(self, entry_idx: int) -> AdmissionStatus:
        plan = self.model.plans.get(entry_idx)
        if plan is None:
            raise AssertionError(f'entry {entry_idx} was never admitted')
        return AdmissionStatus(
            entry_idx=entry_idx,
            complete=plan.complete,
            writeback_seen=plan.writeback_seen,
            flushed=plan.flushed,
            emitted_active=frozenset(plan.emitted_active),
            emitted_empty=frozenset(plan.emitted_empty),
        )

    def restart_entry(self, entry_idx: int):
        """Retire a faulted attempt only after its observed exception writeback.

        The permission is derived from the public writeback snapshot recorded
        while this exact plan was live.  Premature restarts, a second restart
        of the same attempt, and relabelling a successful writeback as an
        exception are rejected; no arbitrary model state is exposed.
        """
        plan = self.model.plans.get(entry_idx)
        if plan is None:
            raise AssertionError(f'entry {entry_idx} was never admitted')
        if plan.flushed:
            raise AssertionError(f'entry {entry_idx} attempt was already restarted')
        evidence = [
            writeback
            for recorded_plan, writeback
            in getattr(self, '_writebacks', {}).get(entry_idx, ())
            if recorded_plan is plan and writeback.entry_idx == entry_idx
        ]
        if not evidence:
            raise AssertionError(
                f'restart of entry {entry_idx} requires an observed writeback '
                'for the current attempt')
        if len(evidence) > 1:
            raise AssertionError(
                f'restart of entry {entry_idx} has {len(evidence)} writebacks; '
                'a duplicated completion cannot authorize a restart')
        if not evidence[0].exception:
            raise AssertionError(
                f'restart of entry {entry_idx} requires an exception writeback; '
                'a successful writeback cannot be relabelled as a fault')
        plan.flushed = True

    def finish(self):
        self.checker.finish()
