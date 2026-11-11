"""VTypeGen leaf DUT: ISA and interface-contract tests.

Expectations are computed by the independent oracle in ``testbenches/vtype_gen/model.py`` from
the RISC-V V specification and the documented VTypeGen state machine. Feature
IDs refer to ``docs/spec/design/functional-points.md``.
"""

from __future__ import annotations

import os
import random

import pytest

from suites.frontend.ibuffer.testbenches.vtype_gen.model import DECODE_WIDTH
from suites.frontend.ibuffer.testbenches.vtype_gen.model import INIT_VTYPE
from suites.frontend.ibuffer.testbenches.vtype_gen.model import Inputs
from suites.frontend.ibuffer.testbenches.vtype_gen.model import VType
from suites.frontend.ibuffer.testbenches.vtype_gen.model import decode_vtype
from suites.frontend.ibuffer.testbenches.vtype_gen.model import encode_vsetivli
from suites.frontend.ibuffer.testbenches.vtype_gen.model import encode_vsetvl
from suites.frontend.ibuffer.testbenches.vtype_gen.model import encode_vsetvli
from suites.frontend.ibuffer.testbenches.vtype_gen.model import instruction_kind
from suites.frontend.ibuffer.testbenches.vtype_gen.model import is_vsetivli
from suites.frontend.ibuffer.testbenches.vtype_gen.model import is_vsetvl
from suites.frontend.ibuffer.testbenches.vtype_gen.model import is_vsetvli
from suites.frontend.ibuffer.testbenches.vtype_gen.model import lane_window

LANE_OFF = ((0, 0),) * DECODE_WIDTH


def payload(vma: int, vta: int, vsew: int, vlmul: int) -> int:
    return (((vma & 1) << 7) | ((vta & 1) << 6) | ((vsew & 7) << 3) | (vlmul & 7))


def vsetvli_lane(*, rd: int = 5, rs1: int = 10, vma: int = 1, vta: int = 1,
                 vsew: int = 2, vlmul: int = 1, reserved: int = 0,
                 valid: int = 1) -> tuple[int, int]:
    return (valid, encode_vsetvli(rd, rs1,
                                  payload(vma, vta, vsew, vlmul) | reserved))


def vsetivli_lane(*, rd: int = 5, uimm: int = 7, vma: int = 0, vta: int = 1,
                  vsew: int = 3, vlmul: int = 0, reserved: int = 0,
                  valid: int = 1) -> tuple[int, int]:
    return (valid, encode_vsetivli(rd, uimm,
                                   payload(vma, vta, vsew, vlmul) | reserved))


def expected_vtype(vsew: int, vlmul: int, *, vma: int = 1, vta: int = 1) -> VType:
    supported, _ = decode_vtype(vsew, vlmul)
    if not supported:
        return INIT_VTYPE
    return VType(illegal=0, vma=vma, vta=vta, vsew=vsew, vlmul=vlmul)


def window(*lanes) -> tuple[tuple[int, int], ...]:
    """Build an 8-lane tuple from sparse ``lane -> (valid, bits)`` overrides."""
    result = list(LANE_OFF)
    for index, value in lanes:
        result[index] = value
    return tuple(result)


# ---------------------------------------------------------------- reset -----
@pytest.mark.feature("IBUF-VTG-008")
async def test_reset_initializes_vill_and_zero_configuration(vtype_gen_agent):
    agent = vtype_gen_agent
    cycle = await agent.cycle(Inputs())
    assert agent.state["vtype_spec"] == INIT_VTYPE.as_dict()
    assert agent.state["vtype_arch"] == INIT_VTYPE.as_dict()
    for lane in range(DECODE_WIDTH):
        assert cycle.before.vtype[lane] == INIT_VTYPE
        assert cycle.before.specvtype[lane] == INIT_VTYPE
    # A second reset from a configured state must return to the same values.
    for _ in range(3):
        await agent.cycle(Inputs(reset=1))
    cycle = await agent.cycle(Inputs())
    assert cycle.before.vtype[0] == INIT_VTYPE


# ------------------------------------------------------------ lane decode ---
@pytest.mark.parametrize("lane", range(DECODE_WIDTH))
@pytest.mark.feature("IBUF-VTG-001")
@pytest.mark.feature("IBUF-VTG-002")
async def test_vsetvli_generates_configuration_on_any_lane(vtype_gen_agent, lane):
    agent = vtype_gen_agent
    new = expected_vtype(vsew=2, vlmul=1)
    cycle = await agent.cycle(Inputs(insts=window((lane, vsetvli_lane()))))
    for index in range(DECODE_WIDTH):
        expected = INIT_VTYPE if index < lane else new
        assert cycle.before.vtype[index] == expected, (lane, index)
    # specvtype is the pre-instruction snapshot.
    for index in range(DECODE_WIDTH):
        assert cycle.before.specvtype[index] == (INIT_VTYPE if index <= lane else new)
    # The gate is low, so the register must not absorb the window.
    assert agent.state["vtype_spec"]["illegal"] == 1


@pytest.mark.feature("IBUF-VTG-001")
async def test_vsetivli_generates_configuration(vtype_gen_agent):
    agent = vtype_gen_agent
    new = expected_vtype(vsew=3, vlmul=0, vma=0, vta=1)
    cycle = await agent.cycle(Inputs(insts=window((0, vsetivli_lane()))))
    assert cycle.before.vtype[0] == new
    assert cycle.before.vtype[1] == new


@pytest.mark.feature("IBUF-VTG-002")
async def test_invalid_lane_does_not_decode_as_vset(vtype_gen_agent):
    agent = vtype_gen_agent
    # The instruction bits match VSETVLI but valid=0: it must pass through.
    cycle = await agent.cycle(Inputs(insts=window(
        (0, vsetvli_lane(valid=0)),
        (1, (1, 0x0000_0013)),
    )))
    for lane in range(DECODE_WIDTH):
        assert cycle.before.vtype[lane] == INIT_VTYPE


@pytest.mark.feature("IBUF-VTG-002")
async def test_vsetvl_encoding_overlaps_vsetvli_at_this_boundary(vtype_gen_agent):
    agent = vtype_gen_agent
    # VTypeGen has no register-form decode: a VSETVL word (funct7=0) matches
    # the VSETVLI pattern and yields the speculative configuration encoded in
    # its rs2 field.  A committed VSETVL flushes the pipeline, which discards
    # that speculation (documented in docs/spec/design/contracts.md, R-VSETVL-OVERLAP).
    word = encode_vsetvl(5, 10, 3)
    cycle = await agent.cycle(Inputs(insts=window((0, (1, word)))))
    assert cycle.before.vtype[0] == VType(0, 0, 0, 0, 3)


@pytest.mark.feature("IBUF-VTG-002")
async def test_non_vset_lanes_pass_the_speculated_configuration(vtype_gen_agent):
    agent = vtype_gen_agent
    new = expected_vtype(vsew=1, vlmul=3)
    await agent.cycle(Inputs(insts=window((0, vsetvli_lane(vsew=1, vlmul=3))),
                             can_update_vtype=1))
    # All eight lanes valid, none is a vset: they all inherit the register.
    lanes = tuple((1, 0x0200_0013 + index) for index in range(DECODE_WIDTH))
    cycle = await agent.cycle(Inputs(insts=lanes))
    for lane in range(DECODE_WIDTH):
        assert cycle.before.vtype[lane] == new, lane
        assert cycle.before.specvtype[lane] == new, lane


# ------------------------------------------------------- SEW/LMUL boundary --
@pytest.mark.feature("IBUF-VTG-003")
async def test_sew_lmul_encoding_table(vtype_gen_agent):
    agent = vtype_gen_agent
    # 64 combinations, eight per cycle.
    for group in range(8):
        lanes = []
        codes = []
        for index in range(8):
            code = group * 8 + index
            vsew, vlmul = code >> 3, code & 7
            lanes.append(vsetvli_lane(vsew=vsew, vlmul=vlmul, vma=index & 1,
                                      vta=(index >> 1) & 1))
            codes.append((vsew, vlmul, index & 1, (index >> 1) & 1))
        cycle = await agent.cycle(Inputs(insts=tuple(lanes)))
        for lane, (vsew, vlmul, vma, vta) in enumerate(codes):
            expected = expected_vtype(vsew, vlmul, vma=vma, vta=vta)
            assert cycle.before.vtype[lane] == expected, (vsew, vlmul)


@pytest.mark.feature("IBUF-VTG-003")
def test_vlmax_matches_the_architectural_table():
    # Independent hand table: VLMAX = LMUL * VLEN / SEW for VLEN=128, ELEN=64.
    table = {
        (0, 0): 16, (0, 1): 32, (0, 2): 64, (0, 3): 128,   # e8 m1/m2/m4/m8
        (0, 5): 2, (0, 6): 4, (0, 7): 8,                    # e8 mf8/mf4/mf2
        (1, 0): 8, (1, 1): 16, (1, 2): 32, (1, 3): 64,      # e16
        (1, 6): 2, (1, 7): 4,                               # e16 mf4/mf2
        (2, 0): 4, (2, 1): 8, (2, 2): 16, (2, 3): 32,       # e32
        (2, 7): 2,                                          # e32 mf2
        (3, 0): 2, (3, 1): 4, (3, 2): 8, (3, 3): 16,        # e64
    }
    legal = set(table)
    for vsew in range(8):
        for vlmul in range(8):
            supported, vlmax = decode_vtype(vsew, vlmul)
            assert supported == ((vsew, vlmul) in legal), (vsew, vlmul)
            if supported:
                assert vlmax == table[(vsew, vlmul)], (vsew, vlmul)
            else:
                assert vlmax == 0


@pytest.mark.feature("IBUF-VTG-004")
async def test_reserved_vtypei_bits_set_vill(vtype_gen_agent):
    agent = vtype_gen_agent
    cycle = await agent.cycle(Inputs(insts=window(
        (0, vsetvli_lane(reserved=0x100)),
        (1, vsetvli_lane(reserved=0x400)),
        (2, vsetivli_lane(reserved=0x200)),
        (3, vsetvli_lane(vsew=2, vlmul=1)),
    )))
    for lane in range(3):
        assert cycle.before.vtype[lane] == INIT_VTYPE, lane
    assert cycle.before.vtype[3] == expected_vtype(2, 1)


@pytest.mark.feature("IBUF-VTG-004")
async def test_reserved_sew_and_lmul_encodings_are_illegal(vtype_gen_agent):
    agent = vtype_gen_agent
    cycle = await agent.cycle(Inputs(insts=window(
        (0, vsetvli_lane(vsew=4, vlmul=0)),   # vsew=100 reserved
        (1, vsetvli_lane(vsew=0, vlmul=4)),   # vlmul=100 reserved
        (2, vsetvli_lane(vsew=3, vlmul=5)),   # e64 > ELEN*mf8
        (3, vsetvli_lane(vsew=2, vlmul=6)),   # e32 > ELEN*mf4
        (4, vsetvli_lane(vsew=1, vlmul=5)),   # e16 > ELEN*mf8
        (5, vsetvli_lane(vsew=0, vlmul=5)),   # e8 mf8 is legal
    )))
    for lane in range(5):
        assert cycle.before.vtype[lane] == INIT_VTYPE, lane
    assert cycle.before.vtype[5] == VType(0, 1, 1, 0, 5)


@pytest.mark.feature("IBUF-VTG-004")
@pytest.mark.feature("IBUF-VTG-007")
async def test_keep_vl_unchanged_vlmax_keeps_configuration(vtype_gen_agent):
    agent = vtype_gen_agent
    base = VType(0, 0, 0, 2, 0)             # e32 m1, VLMAX=4
    await agent.cycle(Inputs(walk_vtype_valid=1, walk_vtype=base))
    # e16 mf2 also has VLMAX=4: the x0/x0 form is legal and changes vtype.
    cycle = await agent.cycle(Inputs(insts=window(
        (0, vsetvli_lane(rd=0, rs1=0, vsew=1, vlmul=7, vma=0, vta=1)))))
    assert cycle.before.vtype[0] == VType(0, 0, 1, 1, 7)
    assert cycle.before.vtype[1] == VType(0, 0, 1, 1, 7)


@pytest.mark.feature("IBUF-VTG-004")
async def test_keep_vl_changed_vlmax_sets_vill(vtype_gen_agent):
    agent = vtype_gen_agent
    base = VType(0, 0, 0, 2, 0)             # e32 m1, VLMAX=4
    await agent.cycle(Inputs(walk_vtype_valid=1, walk_vtype=base))
    # e64 m1 has VLMAX=2: reserved x0/x0 form, vill with the payload retained.
    cycle = await agent.cycle(Inputs(insts=window(
        (0, vsetvli_lane(rd=0, rs1=0, vsew=3, vlmul=0, vma=1, vta=0)))))
    assert cycle.before.vtype[0] == VType(1, 1, 0, 3, 0)


@pytest.mark.feature("IBUF-VTG-007")
async def test_keep_vl_uses_the_nearest_preceding_lane(vtype_gen_agent):
    agent = vtype_gen_agent
    # Start at e8 m1 (VLMAX=16) so a keep-vl e16 mf2 (VLMAX=4) would be
    # illegal if it compared against the register instead of lane 0.
    await agent.cycle(Inputs(walk_vtype_valid=1, walk_vtype=VType(0, 0, 0, 0, 0)))
    cycle = await agent.cycle(Inputs(insts=window(
        (0, vsetvli_lane(vsew=2, vlmul=0, vma=0, vta=0)),          # e32 m1: 4
        (1, vsetvli_lane(rd=0, rs1=0, vsew=1, vlmul=7)),           # e16 mf2: 4
        (2, vsetvli_lane(rd=0, rs1=0, vsew=0, vlmul=6)),           # e8 mf4: 4
        (3, vsetvli_lane(rd=0, rs1=0, vsew=3, vlmul=0)),           # e64 m1: 2
        (4, (1, 0x0000_0013)),
        (5, vsetvli_lane(vsew=0, vlmul=3)),                        # e8 m8: 16
    )))
    assert cycle.before.vtype[0] == VType(0, 0, 0, 2, 0)
    assert cycle.before.vtype[1] == VType(0, 1, 1, 1, 7)
    assert cycle.before.vtype[2] == VType(0, 1, 1, 0, 6)
    assert cycle.before.vtype[3] == VType(1, 1, 1, 3, 0)
    assert cycle.before.vtype[4] == cycle.before.vtype[3]
    assert cycle.before.vtype[5] == VType(0, 1, 1, 0, 3)


# ------------------------------------------------------- state machine ------
@pytest.mark.feature("IBUF-VTG-005")
@pytest.mark.feature("IBUF-VTG-006")
async def test_can_update_vtype_advances_speculation(vtype_gen_agent):
    agent = vtype_gen_agent
    new = expected_vtype(2, 1)
    cycle = await agent.cycle(Inputs(insts=window((0, vsetvli_lane())),
                                     can_update_vtype=1))
    assert cycle.after.vtype[0] == new
    cycle = await agent.cycle(Inputs(insts=((1, 0x13),) * DECODE_WIDTH))
    for lane in range(DECODE_WIDTH):
        assert cycle.before.vtype[lane] == new, lane


@pytest.mark.feature("IBUF-VTG-006")
async def test_can_update_vtype_zero_freezes_speculation(vtype_gen_agent):
    agent = vtype_gen_agent
    await agent.cycle(Inputs(insts=window((0, vsetvli_lane())), can_update_vtype=0))
    cycle = await agent.cycle(Inputs(insts=((1, 0x13),) * DECODE_WIDTH))
    for lane in range(DECODE_WIDTH):
        assert cycle.before.vtype[lane] == INIT_VTYPE, lane


@pytest.mark.feature("IBUF-VTG-005")
async def test_commit_vtype_snapshot_updates_arch_only(vtype_gen_agent):
    agent = vtype_gen_agent
    arch = VType(0, 1, 1, 2, 2)
    await agent.cycle(Inputs(commit_vtype_valid=1, commit_vtype=arch))
    # Speculation is untouched.
    cycle = await agent.cycle(Inputs(insts=((1, 0x13),) * DECODE_WIDTH))
    for lane in range(DECODE_WIDTH):
        assert cycle.before.vtype[lane] == INIT_VTYPE, lane
    # walkToArchVType copies the committed value into speculation.
    await agent.cycle(Inputs(walk_to_arch_vtype=1))
    cycle = await agent.cycle(Inputs(insts=((1, 0x13),) * DECODE_WIDTH))
    for lane in range(DECODE_WIDTH):
        assert cycle.before.vtype[lane] == arch, lane


@pytest.mark.feature("IBUF-VTG-005")
async def test_walk_to_arch_uses_the_pre_edge_arch(vtype_gen_agent):
    agent = vtype_gen_agent
    first = VType(0, 0, 1, 1, 2)
    second = VType(0, 1, 0, 3, 1)
    await agent.cycle(Inputs(commit_vtype_valid=1, commit_vtype=first))
    # arch becomes `second` on this edge, but speculation copies the old value.
    await agent.cycle(Inputs(commit_vtype_valid=1, commit_vtype=second,
                             walk_to_arch_vtype=1))
    cycle = await agent.cycle(Inputs(insts=((1, 0x13),) * DECODE_WIDTH))
    for lane in range(DECODE_WIDTH):
        assert cycle.before.vtype[lane] == first, lane


@pytest.mark.feature("IBUF-VTG-005")
async def test_walk_vtype_has_priority_over_arch_copy(vtype_gen_agent):
    agent = vtype_gen_agent
    arch = VType(0, 1, 0, 0, 3)
    walked = VType(0, 0, 1, 2, 7)
    await agent.cycle(Inputs(commit_vtype_valid=1, commit_vtype=arch))
    await agent.cycle(Inputs(walk_vtype_valid=1, walk_vtype=walked,
                             walk_to_arch_vtype=1))
    cycle = await agent.cycle(Inputs(insts=((1, 0x13),) * DECODE_WIDTH))
    for lane in range(DECODE_WIDTH):
        assert cycle.before.vtype[lane] == walked, lane


@pytest.mark.feature("IBUF-VTG-005")
async def test_commit_vsetvl_updates_both_states_with_priority(vtype_gen_agent):
    agent = vtype_gen_agent
    vsetvl_vtype = VType(0, 1, 1, 2, 1)
    await agent.cycle(Inputs(commit_vtype_valid=1,
                             commit_vtype=VType(0, 0, 0, 0, 0)))
    await agent.cycle(Inputs(commit_has_vsetvl=1, vsetvl_vtype=vsetvl_vtype,
                             walk_vtype_valid=1,
                             walk_vtype=VType(0, 0, 1, 2, 2),
                             can_update_vtype=1,
                             insts=window((0, vsetvli_lane()))))
    cycle = await agent.cycle(Inputs(insts=((1, 0x13),) * DECODE_WIDTH))
    for lane in range(DECODE_WIDTH):
        assert cycle.before.vtype[lane] == vsetvl_vtype, lane
    # The architectural state is the same vsetvl value: copying it back must
    # not change anything.
    await agent.cycle(Inputs(walk_to_arch_vtype=1))
    cycle = await agent.cycle(Inputs(insts=((1, 0x13),) * DECODE_WIDTH))
    assert cycle.before.vtype[0] == vsetvl_vtype


# ---------------------------------------------------------- specvtype -------
@pytest.mark.feature("IBUF-VTG-009")
async def test_specvtype_snapshots_precede_each_lane(vtype_gen_agent):
    agent = vtype_gen_agent
    first = expected_vtype(2, 1)
    second = expected_vtype(0, 3)
    cycle = await agent.cycle(Inputs(insts=window(
        (0, vsetvli_lane(vsew=2, vlmul=1)),
        (1, (1, 0x0000_0013)),
        (2, vsetvli_lane(vsew=0, vlmul=3)),
    )))
    expected_spec = (INIT_VTYPE, first, first, second, second, second, second, second)
    expected_type = (first, first, second, second, second, second, second, second)
    for lane in range(DECODE_WIDTH):
        assert cycle.before.specvtype[lane] == expected_spec[lane], lane
        assert cycle.before.vtype[lane] == expected_type[lane], lane


# ------------------------------------------------------------- encoders -----
@pytest.mark.feature("IBUF-ENV-004")
def test_instruction_encoders_match_the_published_patterns():
    assert is_vsetvli(encode_vsetvli(1, 2, 0xD1))
    assert not is_vsetivli(encode_vsetvli(1, 2, 0xD1))
    assert is_vsetivli(encode_vsetivli(1, 3, 0x58))
    assert is_vsetvl(encode_vsetvl(1, 2, 3))
    assert instruction_kind(encode_vsetvli(1, 2, 0xD1)) == "vsetvli"
    assert instruction_kind(encode_vsetivli(1, 3, 0x58)) == "vsetivli"
    assert instruction_kind(0x0000_0013) is None
    # VSETVLI requires bit 31 == 0; VSETIVLI requires bits 31:30 == 11.
    assert instruction_kind(0x8000_7057) is None      # bits 31:30 == 10
    assert instruction_kind(0xC000_7057) == "vsetivli"
    assert instruction_kind(0x0000_7057) == "vsetvli"
    assert instruction_kind(0x0000_0057) is None      # funct3 != 111
    # A VSETVL encoding (funct7=0) also matches the VSETVLI pattern; only a
    # set vtypei[10:5] distinguishes the immediate form.
    assert is_vsetvl(encode_vsetvl(1, 2, 3))
    assert is_vsetvli(encode_vsetvl(1, 2, 3))
    assert not is_vsetvl(encode_vsetvli(1, 2, 0x21))
    assert is_vsetvli(encode_vsetvli(1, 2, 0x21))


@pytest.mark.feature("IBUF-VTG-003")
def test_lane_window_is_stateless_with_respect_to_non_vset_lanes():
    spec = VType(0, 1, 0, 2, 0)
    lanes = tuple((1, 0x13) for _ in range(DECODE_WIDTH))
    vtype, specvtype = lane_window(lanes, spec)
    assert all(value == spec for value in vtype)
    assert all(value == spec for value in specvtype)


# -------------------------------------------------------------- random ------
@pytest.mark.feature("IBUF-VTG-001")
@pytest.mark.feature("IBUF-VTG-002")
@pytest.mark.feature("IBUF-VTG-003")
@pytest.mark.feature("IBUF-VTG-004")
@pytest.mark.feature("IBUF-VTG-005")
@pytest.mark.feature("IBUF-VTG-006")
@pytest.mark.feature("IBUF-VTG-007")
@pytest.mark.feature("IBUF-VTG-009")
async def test_randomized_windows_and_backend_against_the_oracle(vtype_gen_agent):
    agent = vtype_gen_agent
    seed = int(os.environ.get("UCV_SEED", "1"))
    rng = random.Random(seed * 7919 + 13)

    supported = tuple((vsew, vlmul) for vsew in range(8) for vlmul in range(8)
                      if decode_vtype(vsew, vlmul)[0])

    def backend_vtype() -> VType:
        """Architecturally visible vtype: a supported encoding or the INIT value."""
        if rng.random() < 0.25:
            return INIT_VTYPE
        vsew, vlmul = rng.choice(supported)
        return VType(rng.randrange(2), rng.randrange(2), rng.randrange(2),
                     vsew, vlmul)

    def random_lane():
        choice = rng.random()
        if choice < 0.30:
            reserved = rng.choice((0, 0, 0, 0x100, 0x200, 0x400))
            return vsetvli_lane(rd=rng.choice((0, 0, 1, 5)),
                                rs1=rng.choice((0, 0, 2, 10)),
                                vma=rng.randrange(2), vta=rng.randrange(2),
                                vsew=rng.randrange(8), vlmul=rng.randrange(8),
                                reserved=reserved if reserved < 0x800 else 0,
                                valid=rng.randrange(2))
        if choice < 0.40:
            reserved = rng.choice((0, 0, 0x200, 0x100))
            return vsetivli_lane(rd=rng.choice((0, 0, 3)),
                                 uimm=rng.randrange(32),
                                 vma=rng.randrange(2), vta=rng.randrange(2),
                                 vsew=rng.randrange(8), vlmul=rng.randrange(8),
                                 reserved=reserved if reserved < 0x400 else 0,
                                 valid=rng.randrange(2))
        if choice < 0.50:
            return (rng.randrange(2), rng.getrandbits(32))
        return (rng.randrange(2), rng.getrandbits(32))

    for step in range(240):
        reset = int(rng.random() < 0.02)
        insts = tuple(random_lane() for _ in range(DECODE_WIDTH))
        inputs = Inputs(
            reset=reset,
            insts=insts,
            walk_to_arch_vtype=int(rng.random() < 0.10),
            walk_vtype_valid=int(rng.random() < 0.10),
            walk_vtype=backend_vtype(),
            can_update_vtype=int(rng.random() < 0.60),
            vsetvl_vtype=backend_vtype(),
            commit_vtype_valid=int(rng.random() < 0.10),
            commit_vtype=backend_vtype(),
            commit_has_vsetvl=int(rng.random() < 0.03),
        )
        try:
            await agent.cycle(inputs)
        except BaseException:
            print(f"\nrandom step {step}: {inputs!r}")
            raise
