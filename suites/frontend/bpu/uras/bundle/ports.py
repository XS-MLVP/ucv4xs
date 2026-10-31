"""suites.frontend.bpu.uras.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.ports.bindings import bind_bundle
from suites.frontend.bpu.ports.bindings import ConstantLeaf


@dataclass(frozen=True, slots=True)
class UrasPorts:
    stimulus: PortBinding
    result: PortBinding
    status: PortBinding
    enable_pin: bool = False

    @classmethod
    def bind(cls, dut: Any) -> "UrasPorts":
        io = bind_bundle(dut, ("io",), name="uras.io").bits
        # DefaultConfig MicroRas never reads BasePredictorIO.enable, so firtool
        # removed the pin. Parent-level `rasEnable` gating is therefore not
        # observable at this module boundary; keep it as a Bpu integration
        # obligation rather than fabricating a module pin.
        stimulus = PortBinding(
            dut.clock,
            Bundle(
                s1_fire=io.stageCtrl.s1_fire,
                s2_fire=io.stageCtrl.s2_fire,
                s3_fire=io.stageCtrl.s3_fire,
                has_redirect=io.hasRedirect,
                full_ret_addr=io.fullRetAddr_addr,
                spec_action=io.specIn.attribute_rasAction,
                spec_position=io.specIn.cfiPosition,
                spec_start_pc=io.specIn.startPc_addr,
                s2_valid=io.s2OverrideData.valid,
                s2_action=io.s2OverrideData.bits.attribute_rasAction,
                s2_position=io.s2OverrideData.bits.cfiPosition,
                s2_start_pc=io.s2OverrideData.bits.startPc_addr,
                s3_valid=io.s3OverrideData.valid,
                s3_action=io.s3OverrideData.bits.attribute_rasAction,
                s3_position=io.s3OverrideData.bits.cfiPosition,
                s3_start_pc=io.s3OverrideData.bits.startPc_addr,
            ),
            "uras.stimulus",
        )
        result = PortBinding(
            dut.clock,
            Bundle(usable=io.specOut.isCanUse, target=io.specOut.retTarget_addr),
            "uras.result",
        )
        # MicroRas.scala declares both ready outputs as constant true; the
        # whole-chip build folded the pins away.
        status = PortBinding(
            dut.clock,
            Bundle(reset_done=ConstantLeaf(1), train_ready=ConstantLeaf(1)),
            "uras.status",
        )
        return cls(stimulus, result, status)
