"""bpuverify.ras.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.bundle.bindings import PulseBinding
from bpuverify.common.bundle.bindings import bind_bundle
from bpuverify.common.bundle.bindings import bind_pulse


@dataclass(frozen=True, slots=True)
class RasPorts:
    speculative: PulseBinding
    redirect: PulseBinding
    commit: PulseBinding
    state: PortBinding
    status: PortBinding

    @classmethod
    def bind(cls, dut: Any) -> "RasPorts":
        io = bound_io = bind_bundle(dut, ("io",), name="ras.io").bits
        spec = bind_pulse(dut, ("io", "specIn"), name="ras.speculative")
        speculative = PulseBinding(
            spec.clock,
            spec.valid,
            Bundle(
                enable=io.enable,
                action=spec.bits.attribute.rasAction,
                branch_type=spec.bits.attribute.branchType,
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
                    "action": "attribute.rasAction",
                    "branch_type": "attribute.branchType",
                    "meta": "meta.ras",
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
                    "action": "attribute.rasAction",
                    "branch_type": "attribute.branchType",
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
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=io.sramResetDone, train_ready=io.trainReady),
            "ras.status",
        )
        return cls(speculative, redirect, commit, state, status)
