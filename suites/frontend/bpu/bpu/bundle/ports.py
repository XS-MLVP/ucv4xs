"""suites.frontend.bpu.bpu.bundle.ports components."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from toffee import Bundle
from toffee import ReadyValid
from toffee import Role
from toffee import DriveStable, Value
from toffee.data import signal_width
from suites.frontend.bpu.models.configuration import PHR_STORAGE_BITS
from suites.frontend.bpu.ports.bindings import ConstantLeaf
from suites.frontend.bpu.ports.bindings import PortBinding
from suites.frontend.bpu.ports.bindings import PulseBinding
from suites.frontend.bpu.ports.bindings import bind_bundle
from suites.frontend.bpu.ports.bindings import bind_pulse


class BpuMetadataPort(ReadyValid):
    """Adapt the valid-only metadata channel to the SDK transfer monitor.

    ``ready`` is a read-only protocol constant, NOT a generated input and NOT
    part of any driver's ownership. The trigger retains the SDK monitor's
    normal pre-edge snapshot/next-edge timestamp without inventing a handshake.
    """
    @property
    def fire(self):
        return Value(self.valid, 1, sample=DriveStable(self.clock), mode='each_sample')


def validate_consumed_ports(io):
    """The reviewed integrated DefaultConfig projection, not optional pin loss.

    In particular, an accidentally removed sampled field must not be mistaken
    for a newly DCE'd capability. A changed generated ABI needs a new review.
    """
    port = io.toFtq
    for name, node, fields in (
        ('toFtq', port, {'meta', 'prediction', 's2FtqPtr', 's3FtqPtr'}),
        ('prediction', port.prediction, {'valid', 'ready', 'bits'}),
        ('prediction.bits', port.prediction.bits,
         {'startPc_addr', 'taken', 'endPosition', 's2Override', 's3Override'}),
        ('meta', port.meta, {'valid', 'bits'}),
        ('meta.bits', port.meta.bits, {'resolveMeta', 'redirectMeta', 'commitMeta_ras'}),
    ):
        if set(node) != fields:
            raise ValueError(f'BPU integrated {name} fields changed: expected {sorted(fields)}, got {sorted(node)}')
    leaves = (
        ('prediction.valid', port.prediction.valid, 1, 'output'),
        ('prediction.ready', port.prediction.ready, 1, 'input'),
        ('prediction.startPc', port.prediction.bits.startPc_addr, 50, 'output'),
        ('prediction.taken', port.prediction.bits.taken, 1, 'output'),
        ('prediction.endPosition', port.prediction.bits.endPosition, 5, 'output'),
        ('prediction.s2Override', port.prediction.bits.s2Override, 1, 'output'),
        ('prediction.s3Override', port.prediction.bits.s3Override, 1, 'output'),
        ('meta.valid', port.meta.valid, 1, 'output'),
    )
    for name, leaf, width, direction in leaves:
        if signal_width(leaf) != width:
            raise ValueError(f'BPU integrated {name} width must be {width}')
        if not (leaf.IsInIO() if direction == 'input' else leaf.IsOutIO()):
            raise ValueError(f'BPU integrated {name} direction must be {direction}')


def metadata_with_phr(node, *, direction):
    """Logical PHR names over the real flattened, value-only ABI.

    Other metadata remains exactly as exported. No pointer flag/epoch is
    invented; environment transaction identity is separate from this payload.
    """
    phr = node.phr
    if set(phr) != {'phrPtr_value', 'phrLowBits'}:
        raise ValueError('BPU PHR metadata fields changed; value-only ABI requires review')
    for name, width in (('phrPtr_value', (PHR_STORAGE_BITS - 1).bit_length()), ('phrLowBits', 13)):
        leaf = phr[name]
        if signal_width(leaf) != width:
            raise ValueError(f'BPU PHR {name} width must be {width}')
        if not (leaf.IsInIO() if direction == 'input' else leaf.IsOutIO()):
            raise ValueError(f'BPU PHR {name} direction must be {direction}')
    return Bundle(**{name: value for name, value in node.items() if name != 'phr'},
                  phr=Bundle(phrPtr=Bundle(value=phr.phrPtr_value), phrLowBits=phr.phrLowBits))


def validate_training_geometry(start_pcs):
    if len(start_pcs) != 3 or tuple(map(len, start_pcs)) != (1, 1, 2):
        raise ValueError('BPU training PC copies must retain the reviewed (1,1,2) projection')
    for copy in start_pcs:
        for pc in copy:
            if set(pc) != {'addr'} or signal_width(pc.addr) != 49 or not pc.addr.IsInIO():
                raise ValueError('BPU training PCs require actual 49-bit input addresses')


@dataclass(frozen=True, slots=True)
class BpuPorts:
    control: PortBinding
    training: ReadyValid
    redirect: PulseBinding
    prediction: ReadyValid
    meta: ReadyValid
    prediction_target_observable: bool
    meta_perf_observable: bool

    @classmethod
    def bind(cls, dut: Any) -> "BpuPorts":
        io = bind_bundle(dut, ("io",), name="bpu.io").bits
        validate_consumed_ports(io)
        control = PortBinding(
            dut.clock,
            Bundle(
                reset_vector=io.resetVector_addr,
                prediction_ready=io.toFtq.prediction.ready,
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
        validate_training_geometry(tuple(tuple(copy) for copy in train.bits.startPcVec_dup))
        training = ReadyValid(
            clock=dut.clock,
            valid=train.valid,
            ready=train.ready,
            bits=Bundle(
                meta=metadata_with_phr(train.bits.meta, direction='input'),
                start_pcs=train.bits.startPcVec_dup,
                branches=tuple(train.bits.branches),
            ),
            role=Role.PRODUCER,
            name="bpu.training",
        )

        prediction_port = io.toFtq.prediction
        prediction_fields = dict(
            start_pc=prediction_port.bits.startPc_addr,
            taken=prediction_port.bits.taken,
            position=prediction_port.bits.endPosition,
            s2_override=prediction_port.bits.s2Override,
            s3_override=prediction_port.bits.s3Override,
        )
        prediction = ReadyValid(
            clock=dut.clock,
            valid=prediction_port.valid,
            ready=prediction_port.ready,
            bits=Bundle(**prediction_fields),
            role=Role.MONITOR,
            name="bpu.prediction",
        )

        meta_port = io.toFtq.meta
        meta_fields = dict(resolve=metadata_with_phr(meta_port.bits.resolveMeta, direction='output'),
                           redirect=metadata_with_phr(meta_port.bits.redirectMeta, direction='output'))
        meta = BpuMetadataPort(
            clock=dut.clock,
            valid=meta_port.valid,
            ready=ConstantLeaf(1),
            bits=Bundle(**meta_fields),
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
        redirect = PulseBinding(redirect.clock, redirect.valid,
            Bundle(**{name: value for name, value in redirect.bits.items() if name != 'meta'},
                   meta=metadata_with_phr(redirect.bits.meta, direction='input')), redirect.name)
        return cls(control, training, redirect, prediction, meta, False, False)
