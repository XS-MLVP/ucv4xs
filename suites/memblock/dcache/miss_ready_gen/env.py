"""Port-level environment for the pure-combinational MissReadyGen."""
from __future__ import annotations

from .coverage import MissReadyGenCoverage

CH0_FIELDS = {
    "source": 4, "pf_source": 3, "cmd": 5, "addr": 48, "vaddr": 50,
    "vaddrAlias": 2, "vaddrSet": 8, "full_overwrite": 1, "word_idx": 3,
    "amo_data": 128, "amo_mask": 16, "amo_cmp": 128, "req_coh_state": 2,
    "id": 6, "isBtoT": 1, "occupy_way": 4, "cancel": 1,
    "store_data": 512, "store_mask": 64,
}
CH_FIELDS = {
    "source": 4, "cmd": 5, "addr": 48, "vaddr": 50, "vaddrAlias": 2,
    "vaddrSet": 8, "req_coh_state": 2, "id": 6, "isBtoT": 1,
    "occupy_way": 4, "cancel": 1, "isSpecMiss": 1,
}


class MissReadyGenEnv:
    def __init__(self, dut, coverage: MissReadyGenCoverage | None = None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.ready = [getattr(dut, f"io_queryMQ_{ch}_ready") for ch in range(4)]
        self.in_valid = [getattr(dut, f"io_in_{ch}_valid") for ch in range(4)]
        self.in_ready = [getattr(dut, f"io_in_{ch}_ready") for ch in range(4)]
        self.out_valid = [getattr(dut, f"io_queryMQ_{ch}_req_valid") for ch in range(4)]
        self.in_bits = []
        self.out_bits = []
        for ch in range(4):
            fields = CH0_FIELDS if ch == 0 else CH_FIELDS
            self.in_bits.append({name: getattr(dut, f"io_in_{ch}_bits_{name}")
                                 for name in fields})
            self.out_bits.append({name: getattr(dut, f"io_queryMQ_{ch}_req_bits_{name}")
                                  for name in fields})
        self.vectors = 0

    # ---------------------------------------------------------------- drive
    def drive(self, channel: int, valid: bool, fields: dict[str, int]) -> None:
        self.in_valid[channel].Set(1 if valid else 0)
        for name, signal in self.in_bits[channel].items():
            signal.Set(fields.get(name, 0))

    def drive_ready(self, ready_mask: int) -> None:
        for ch, signal in enumerate(self.ready):
            signal.Set((ready_mask >> ch) & 1)

    def eval(self) -> None:
        self.dut.Step(1)

    # ---------------------------------------------------------------- check
    def check(self, context: str = "vector") -> dict:
        mapping = []
        for ch in range(4):
            got_valid = int(self.out_valid[ch].value)
            want_valid = int(self.in_valid[ch].value)
            if got_valid != want_valid:
                raise AssertionError(
                    f"{context}: channel {ch} valid {got_valid} != {want_valid}")
            got_ready = int(self.in_ready[ch].value)
            want_ready = int(self.ready[ch].value)
            if got_ready != want_ready:
                raise AssertionError(
                    f"{context}: channel {ch} ready {got_ready} != {want_ready}")
            for name, payload_signal in self.in_bits[ch].items():
                want = int(payload_signal.value)
                got = int(self.out_bits[ch][name].value)
                if got != want:
                    raise AssertionError(
                        f"{context}: channel {ch} field {name} {got:#x} != {want:#x}")
            mapping.append((ch, got_valid, got_ready))
        self.vectors += 1
        if self.coverage is not None:
            ready_mask = sum((int(signal.value) & 1) << ch
                             for ch, signal in enumerate(self.ready))
            for ch, valid, _ready in mapping:
                self.coverage.sample_channel(
                    ch, valid, ready_mask,
                    "wide" if ch == 0 else "narrow")
        return {"valid": [m[1] for m in mapping],
                "ready": [m[2] for m in mapping]}

    def payload_digest(self, channel: int) -> dict[str, int]:
        return {name: int(signal.value) for name, signal in self.in_bits[channel].items()}
