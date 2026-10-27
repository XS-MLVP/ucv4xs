"""bpuverify.bpu.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from toffee import ReadyValid
from toffee import Role
from toffee import DriveStable, Value
from bpuverify.common.bundle.bindings import PortBinding
from bpuverify.common.bundle.bindings import PulseBinding
from bpuverify.common.bundle.bindings import bind_bundle
from bpuverify.common.bundle.bindings import bind_pulse


class BpuMetadataPort(ReadyValid):
    """Generated IO has ready; the BPU's metadata protocol is valid-only.

    Keep every physical binding truthful. The public trigger specialization
    lets the existing SDK monitor retain its normal pre-edge snapshot/next-edge
    timestamp without copying queues, patching SDK internals or faking ready.
    """
    @property
    def fire(self):
        return Value(self.valid, 1, sample=DriveStable(self.clock), mode='each_sample')


@dataclass(frozen=True, slots=True)
class BpuPorts:
    control: PortBinding
    training: ReadyValid
    redirect: PulseBinding
    prediction: ReadyValid
    meta: ReadyValid

    @classmethod
    def bind(cls, dut: Any) -> "BpuPorts":
        io = bind_bundle(dut, ("io",), name="bpu.io").bits
        control = PortBinding(
            dut.clock,
            Bundle(
                reset_vector=io.resetVector_addr,
                prediction_ready=io.toFtq.prediction.ready,
                meta_ready=io.toFtq.meta.ready,
                ubtb_enable=io.ctrl.ubtbEnable,
                abtb_enable=io.ctrl.abtbEnable,
                mbtb_enable=io.ctrl.mbtbEnable,
                tage_enable=io.ctrl.tageEnable,
                sc_enable=io.ctrl.scEnable,
                ittage_enable=io.ctrl.ittageEnable,
                ras_enable=io.ctrl.rasEnable,
            ),
            "bpu.control",
        )

        train = io.fromFtq.train
        training = ReadyValid(
            clock=dut.clock,
            valid=train.valid,
            ready=train.ready,
            bits=Bundle(
                meta=train.bits.meta,
                start_pcs=train.bits.startPcVec_dup,
                branches=tuple(train.bits.branches),
            ),
            role=Role.PRODUCER,
            name="bpu.training",
        )

        prediction_port = io.toFtq.prediction
        prediction = ReadyValid(
            clock=dut.clock,
            valid=prediction_port.valid,
            ready=prediction_port.ready,
            bits=Bundle(
                start_pc=prediction_port.bits.startPc_addr,
                target=prediction_port.bits.target_addr,
                taken=prediction_port.bits.taken,
                position=prediction_port.bits.endPosition,
                s2_override=prediction_port.bits.s2Override,
                s3_override=prediction_port.bits.s3Override,
            ),
            role=Role.MONITOR,
            name="bpu.prediction",
        )

        meta_port = io.toFtq.meta
        perf_port = io.toFtq.perfMeta
        # perfMeta has no valid of its own; sample it with the S3 meta handshake.
        meta = BpuMetadataPort(
            clock=dut.clock,
            valid=meta_port.valid,
            ready=meta_port.ready,
            bits=Bundle(
                resolve=meta_port.bits.resolveMeta,
                redirect=meta_port.bits.redirectMeta,
                perf=Bundle(
                    start_pc=perf_port.startPc_addr,
                    s1_target=perf_port.s1Prediction.target_addr,
                    s1_taken=perf_port.s1Prediction.taken,
                    s1_position=perf_port.s1Prediction.cfiPosition,
                    s1_source=perf_port.bpSource.s1Source,
                ),
            ),
            role=Role.MONITOR,
            name="bpu.meta",
        )

        full_redirect = bind_pulse(
            dut, ("io", "fromFtq", "redirect"), name="bpu.redirect"
        )
        redirect = PulseBinding(
            full_redirect.clock,
            full_redirect.valid,
            full_redirect.bits.view_as(
                {
                    "meta": "meta",
                    "cfi_pc": "cfiPc_addr",
                    "target": "target_addr",
                    "taken": "taken",
                    "branch_type": "attribute.branchType",
                    "ras_action": "attribute.rasAction",
                },
                path="bpu.redirect.bits",
            ),
            full_redirect.name,
        )
        return cls(control, training, redirect, prediction, meta)
