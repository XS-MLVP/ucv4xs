"""Independent RISC-V V-extension vtype oracle for the VTypeGen leaf DUT.

Expected values come from the ratified RISC-V "V" Vector Extension 1.0
specification and the documented VTypeGen interface:

* ``vtype`` is ``{vill, 0..., vma, vta, vsew[2:0], vlmul[2:0]}``; ``vill`` is
  set when the requested SEW/LMUL combination is unsupported, and then the
  configuration fields read back as zero.
* ``VLMAX = LMUL * VLEN / SEW`` with VLEN=128, ELEN=64 for DefaultConfig.
* ``VLEN/ELEN`` bound the legal SEW: the implementation supports e8/e16/e32/e64
  and mf8/mf4/mf2/m1/m2/m4/m8; ``vlmul=100`` is reserved and every SEW wider
  than ``ELEN * min(LMUL,1)`` is unsupported.
* ``vsetvli``/``vsetivli`` write the new configuration; the ``rd=x0, rs1=x0``
  form keeps ``vl`` and is *reserved* when the new SEW/LMUL changes VLMAX.
  Implementations may set ``vill``; this design does, and that decision is the
  interface contract recorded in ``docs/spec/design/contracts.md``.
* A lane whose instruction is not a vset instruction passes the current
  speculated vtype through unchanged.  VTypeGen evaluates all eight decode
  lanes combinationally and chains vset results within the window.

The model never reads generated RTL.  It also implements the documented
speculated/architectural state machine (not invented here, taken from the
VTypeGen interface contract): a committed ``vsetvl`` wins over a committed
vtype snapshot, which wins over a walk-vtype update, which wins over
``walkToArchVType``, which wins over the newly decoded window.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

VLEN = 128
ELEN = 64
DECODE_WIDTH = 8

SEW_BY_CODE = {0: 8, 1: 16, 2: 32, 3: 64}
LMUL_BY_CODE = {
    0: Fraction(1),
    1: Fraction(2),
    2: Fraction(4),
    3: Fraction(8),
    5: Fraction(1, 8),
    6: Fraction(1, 4),
    7: Fraction(1, 2),
    # 4 (100) is reserved by the ISA.
}


class StimulusError(ValueError):
    """The environment supplied an input the interface contract forbids."""


def binary(value: int, name: str) -> int:
    if not isinstance(value, int) or value not in (0, 1):
        raise StimulusError(f"{name} must be 0 or 1")
    return value


def decode_vtype(vsew: int, vlmul: int) -> tuple[bool, int]:
    """Return (supported, VLMAX) for one vsew/vlmul encoding pair."""
    if vsew not in SEW_BY_CODE or vlmul not in LMUL_BY_CODE:
        return False, 0
    lmul = LMUL_BY_CODE[vlmul]
    sew = SEW_BY_CODE[vsew]
    if sew > min(lmul, 1) * ELEN:
        return False, 0
    vlmax = VLEN * lmul / sew
    if vlmax.denominator != 1:
        raise AssertionError(f"non-integral VLMAX for vsew={vsew} vlmul={vlmul}")
    return True, int(vlmax)


@dataclass(frozen=True)
class VType:
    illegal: int = 1
    vma: int = 0
    vta: int = 0
    vsew: int = 0
    vlmul: int = 0

    def __post_init__(self) -> None:
        for name in ("illegal", "vma", "vta"):
            binary(getattr(self, name), name)
        if not isinstance(self.vsew, int) or not 0 <= self.vsew < 8:
            raise StimulusError("vsew must be a 3-bit value")
        if not isinstance(self.vlmul, int) or not 0 <= self.vlmul < 8:
            raise StimulusError("vlmul must be a 3-bit value")

    @property
    def supported(self) -> bool:
        return self.illegal == 0 and decode_vtype(self.vsew, self.vlmul)[0]

    @property
    def vlmax(self) -> int:
        return decode_vtype(self.vsew, self.vlmul)[1] if self.illegal == 0 else 0

    def as_dict(self) -> dict[str, int]:
        return {"illegal": self.illegal, "vma": self.vma, "vta": self.vta,
                "vsew": self.vsew, "vlmul": self.vlmul}


INIT_VTYPE = VType()

_VSET_OPCODE = 0x57          # 1010111
_FUNCT3 = 7 << 12
_VSETVLI_MASK = (1 << 31) | _FUNCT3 | 0x7F
_VSETVLI_MATCH = _FUNCT3 | _VSET_OPCODE
_VSETIVLI_MASK = (3 << 30) | _FUNCT3 | 0x7F
_VSETIVLI_MATCH = (3 << 30) | _FUNCT3 | _VSET_OPCODE
_VSETVL_MASK = (0x7F << 25) | _FUNCT3 | 0x7F
_VSETVL_MATCH = _FUNCT3 | _VSET_OPCODE


def _instruction(bits: int) -> int:
    if not isinstance(bits, int) or not 0 <= bits < (1 << 32):
        raise StimulusError("instruction bits must be an unsigned 32-bit value")
    return bits


def is_vsetvli(bits: int) -> bool:
    """VSETVLI pattern: bit 31 == 0, funct3=111, opcode=1010111.

    The VSETVL encoding (funct7=0) is a sub-pattern of this one; the main
    decoder owns that distinction and a committed VSETVL flushes the pipeline.
    """
    return _instruction(bits) & _VSETVLI_MASK == _VSETVLI_MATCH


def is_vsetivli(bits: int) -> bool:
    """VSETIVLI pattern: bits 31:30 == 11, funct3=111, opcode=1010111."""
    return _instruction(bits) & _VSETIVLI_MASK == _VSETIVLI_MATCH


def is_vsetvl(bits: int) -> bool:
    """VSETVL pattern: funct7=0, funct3=111, opcode=1010111."""
    return _instruction(bits) & _VSETVL_MASK == _VSETVL_MATCH


def instruction_kind(bits: int) -> str | None:
    """Classify one 32-bit decode lane the way VTypeGen does.

    VTypeGen only recognises the two immediate forms; the register form is
    handled at commit.  A VSETVL word therefore overlaps VSETVLI here and
    produces a speculative configuration that the pipeline flush discards.
    """
    if is_vsetivli(bits):
        return "vsetivli"
    if is_vsetvli(bits):
        return "vsetvli"
    return None


def instruction_rd(bits: int) -> int:
    return (bits >> 7) & 0x1F


def instruction_rs1(bits: int) -> int:
    return (bits >> 15) & 0x1F


def encode_vsetvli(rd: int, rs1: int, vtypei: int) -> int:
    """Assemble one ``vsetvli`` word (rd/rs1 are architectural indices)."""
    if not 0 <= vtypei < (1 << 11):
        raise ValueError("vtypei must be 11 bits")
    return ((vtypei & 0x7FF) << 20) | ((rs1 & 0x1F) << 15) | ((7) << 12) \
        | ((rd & 0x1F) << 7) | _VSET_OPCODE


def encode_vsetivli(rd: int, uimm: int, vtypei: int) -> int:
    """Assemble one ``vsetivli`` word (uimm is the 5-bit AVL immediate)."""
    if not 0 <= vtypei < (1 << 10):
        raise ValueError("vtypei must be 10 bits")
    if not 0 <= uimm < 32:
        raise ValueError("uimm must be 5 bits")
    return ((3 << 30) | ((vtypei & 0x3FF) << 20) | ((uimm & 0x1F) << 15)
            | (7 << 12) | ((rd & 0x1F) << 7) | _VSET_OPCODE)


def encode_vsetvl(rd: int, rs1: int, rs2: int) -> int:
    """Assemble one ``vsetvl`` word (funct7=0, rs2 carries the vtype)."""
    return (((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15)
            | (7 << 12) | ((rd & 0x1F) << 7) | _VSET_OPCODE)


def vtype_from_instruction(bits: int, kind: str) -> VType:
    """Decode the requested configuration exactly as the ISA defines it.

    ``vsetvli`` carries an 11-bit ``vtypei``; its bits above the 8-bit
    ``vtype`` payload are reserved and must read zero.  ``vsetivli`` carries a
    10-bit ``vtypei``.  Any reserved bit or unsupported SEW/LMUL combination
    produces ``vill=1`` with every configuration field zero.
    """
    if kind == "vsetvli":
        immediate = (bits >> 20) & 0x7FF
        reserved = immediate >> 8
    elif kind == "vsetivli":
        immediate = (bits >> 20) & 0x3FF
        reserved = immediate >> 8
    else:
        raise ValueError(f"{kind} does not carry a vtype immediate")
    payload = immediate & 0xFF
    vsew = (payload >> 3) & 0x7
    vlmul = payload & 0x7
    supported, _ = decode_vtype(vsew, vlmul)
    if reserved or not supported:
        return VType(illegal=1)
    return VType(illegal=0,
                 vma=(payload >> 7) & 1,
                 vta=(payload >> 6) & 1,
                 vsew=vsew,
                 vlmul=vlmul)


def lane_window(insts, spec: VType) -> tuple[tuple[VType, ...], tuple[VType, ...]]:
    """Evaluate the eight decode lanes combinationally.

    Returns ``(vtype, specvtype)``:

    * ``vtype[i]`` is the configuration attached to lane ``i``: a vset lane
      produces its own new configuration (or ``vill``), any other lane passes
      the previous lane's result through.
    * ``specvtype[i]`` is the *pre-instruction* snapshot (the speculated
      configuration before lane ``i`` applies its own vset), matching the
      interface description "speculated vtype for snapshot".
    """
    if len(insts) != DECODE_WIDTH:
        raise ValueError(f"VTypeGen expects {DECODE_WIDTH} decode lanes")
    requested: list[VType | None] = []
    candidate_vlmax: list[int] = []
    base_illegal: list[bool] = []
    for valid, bits in insts:
        binary(valid, "inst.valid")
        kind = instruction_kind(bits) if valid else None
        if kind not in ("vsetvli", "vsetivli"):
            requested.append(None)
            candidate_vlmax.append(0)
            base_illegal.append(False)
            continue
        new = vtype_from_instruction(bits, kind)
        requested.append(new)
        # The VLMAX decode uses the requested SEW/LMUL payload even when the
        # instruction is illegal (reserved vtypei bits or the x0/x0 reserved
        # form); an unsupported SEW/LMUL encoding decodes to zero.
        payload = ((bits >> 20) & 0xFF)
        candidate_vlmax.append(decode_vtype((payload >> 3) & 7, payload & 7)[1])
        base_illegal.append(bool(new.illegal))

    # VLMAX before each lane, following the ISA reserved-case rule through the
    # same window: a vset lane changes the reference for the following lanes.
    # The register reference decodes the stored SEW/LMUL fields even when the
    # register is marked illegal (its payload is zero at reset -> e8/m1).
    previous_vlmax = []
    running = decode_vtype(spec.vsew, spec.vlmul)[1]
    for lane in range(DECODE_WIDTH):
        previous_vlmax.append(running)
        if requested[lane] is not None:
            running = candidate_vlmax[lane]

    chain: list[VType] = []
    snapshots: list[VType] = []
    for lane in range(DECODE_WIDTH):
        snapshots.append(spec if lane == 0 else chain[lane - 1])
        new = requested[lane]
        if new is None:
            chain.append(spec if lane == 0 else chain[lane - 1])
            continue
        if not base_illegal[lane] and instruction_rd(insts[lane][1]) == 0 \
                and instruction_rs1(insts[lane][1]) == 0 \
                and candidate_vlmax[lane] != previous_vlmax[lane]:
            # Reserved ``vset{i}vli x0, x0`` with a VLMAX change: the design
            # may and does report vill.  It keeps the requested encoding in
            # the internal payload, which is an interface don't-care under
            # vill (see docs/spec/design/contracts.md, R-VILL-PAYLOAD).
            chain.append(VType(illegal=1, vma=new.vma, vta=new.vta,
                               vsew=new.vsew, vlmul=new.vlmul))
        else:
            chain.append(new)
    return tuple(chain), tuple(snapshots)


@dataclass(frozen=True)
class Inputs:
    """One cycle of VTypeGen stimulus.  Reset is asynchronous in the DUT."""

    reset: int = 0
    insts: tuple[tuple[int, int], ...] = ((0, 0),) * DECODE_WIDTH
    walk_to_arch_vtype: int = 0
    walk_vtype_valid: int = 0
    walk_vtype: VType = INIT_VTYPE
    can_update_vtype: int = 0
    vsetvl_vtype: VType = INIT_VTYPE
    commit_vtype_valid: int = 0
    commit_vtype: VType = INIT_VTYPE
    commit_has_vsetvl: int = 0

    def __post_init__(self) -> None:
        for name in ("reset", "walk_to_arch_vtype", "walk_vtype_valid",
                     "can_update_vtype", "commit_vtype_valid", "commit_has_vsetvl"):
            binary(getattr(self, name), name)
        if not isinstance(self.insts, tuple) or len(self.insts) != DECODE_WIDTH:
            raise StimulusError(f"insts must be a tuple of {DECODE_WIDTH} lanes")
        for valid, bits in self.insts:
            binary(valid, "inst.valid")
            if not isinstance(bits, int) or not 0 <= bits < (1 << 32):
                raise StimulusError("inst.bits must be unsigned 32-bit")
        for name in ("walk_vtype", "vsetvl_vtype", "commit_vtype"):
            value = getattr(self, name)
            if not isinstance(value, VType):
                raise StimulusError(f"{name} must be a VType")
            # These inputs come from the architectural vtype path.  A vtype
            # with a reserved SEW/LMUL encoding cannot be architecturally
            # visible: the producer zeroes the payload when it raises vill.
            if not decode_vtype(value.vsew, value.vlmul)[0]:
                raise StimulusError(
                    f"{name} uses a reserved or unsupported SEW/LMUL encoding")


@dataclass(frozen=True)
class Outputs:
    vtype: tuple[VType, ...]
    specvtype: tuple[VType, ...]


class VTypeGenModel:
    """Cycle model of the speculated/architectural vtype state machine."""

    def __init__(self) -> None:
        self.spec = INIT_VTYPE
        self.arch = INIT_VTYPE

    def reset_state(self) -> None:
        self.spec = INIT_VTYPE
        self.arch = INIT_VTYPE

    def outputs(self, inputs: Inputs) -> Outputs:
        if not isinstance(inputs, Inputs):
            raise TypeError("VTypeGen model requires semantic Inputs")
        spec = INIT_VTYPE if inputs.reset else self.spec
        vtype, specvtype = lane_window(inputs.insts, spec)
        return Outputs(vtype=vtype, specvtype=specvtype)

    def tick(self, inputs: Inputs) -> None:
        if not isinstance(inputs, Inputs):
            raise TypeError("VTypeGen model requires semantic Inputs")
        if inputs.reset:
            self.reset_state()
            return
        vtype, _ = lane_window(inputs.insts, self.spec)

        arch = self.arch
        if inputs.commit_has_vsetvl:
            arch = inputs.vsetvl_vtype
        elif inputs.commit_vtype_valid:
            arch = inputs.commit_vtype

        spec = self.spec
        if inputs.commit_has_vsetvl:
            spec = inputs.vsetvl_vtype
        elif inputs.walk_vtype_valid:
            spec = inputs.walk_vtype
        elif inputs.walk_to_arch_vtype:
            spec = self.arch          # the architectural value *before* this edge
        elif inputs.can_update_vtype:
            spec = vtype[-1]

        self.spec, self.arch = spec, arch

    def snapshot(self) -> dict[str, object]:
        return {"vtype_spec": self.spec.as_dict(), "vtype_arch": self.arch.as_dict()}
