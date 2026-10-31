"""suites.frontend.bpu.ras.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from suites.frontend.bpu.ports.bindings import ConstantLeaf
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.ports.bindings import PulseBinding
from suites.frontend.bpu.ports.bindings import bind_bundle
from suites.frontend.bpu.ports.bindings import bind_pulse


@dataclass(frozen=True, slots=True)
class RasPorts:
    control: PortBinding
    speculative: PulseBinding
    redirect: PulseBinding
    commit: PulseBinding
    state: PortBinding
    status: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "RasPorts":
        io = bound_io = bind_bundle(dut, ("io",), name="ras.io").bits
        control = PortBinding(dut.clock, Bundle(enable=io.enable), "ras.control")
        spec = bind_pulse(dut, ("io", "specIn"), name="ras.speculative")
        # Whole-chip DCE flattened the branch attribute to its RAS action
        # leaf; Ras does not consume branchType.
        speculative = PulseBinding(
            spec.clock,
            spec.valid,
            Bundle(
                action=spec.bits.attribute_rasAction,
                position=spec.bits.cfiPosition,
                start_pc=spec.bits.startPc,
            ),
            spec.name,
        )
        full_redirect = bind_pulse(dut, ("io", "redirect"), name="ras.redirect")
        redirect = PulseBinding(
            full_redirect.clock,
            full_redirect.valid,
            full_redirect.bits.view_as(
                {
                    "action": "attribute_rasAction",
                    "meta": "meta_ras",
                    "cfi_pc": "cfiPc_addr",
                },
                path="ras.redirect.bits",
            ),
            full_redirect.name,
        )
        full_commit = bind_pulse(dut, ("io", "commit"), name="ras.commit")
        commit = PulseBinding(
            full_commit.clock,
            full_commit.valid,
            full_commit.bits.view_as(
                {
                    "action": "attribute_rasAction",
                    "meta": "meta_ras",
                },
                path="ras.commit.bits",
            ),
            full_commit.name,
        )
        state = PortBinding(
            dut.clock,
            Bundle(
                top=bound_io.topRetAddr_addr,
                redirect_meta=bound_io.redirectMeta,
                commit_meta=bound_io.commitMeta,
            ),
            "ras.state",
        )
        # MicroRas.scala declares both readiness bits as constants; whole-chip
        # DCE removed the pins. Preserve the declared post-reset contract.
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=ConstantLeaf(1), train_ready=ConstantLeaf(1)),
            "ras.status",
        )
        return cls(control, speculative, redirect, commit, state, status)
