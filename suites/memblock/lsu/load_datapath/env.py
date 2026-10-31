"""Environment and independent reference for LoadUnitDataPath.

The unit is a two-stage byte pipeline plus a rotate/extend network:

* **S1→S2**: metadata register (bank offset, fuOpType, fpWen, replay flags,
  unalign-head), plus the valid chain.
* **S2→S3**: per-byte data merge, then the rotate/extension decode registers.
* **S3→S4**: `s4ShiftHead` holds the previous cycle's rotated head data, which
  the tail path ORs with the tail's left-shifted data.
* **Outputs**: `s3ShiftData` is a byte rotation (or the head/tail merge) and
  `s3ShiftAndExtData` is the NaN-boxed / sign-extended 64-bit value.

Per-byte merge priority (each byte independently):

    1. sqForward.forwardMask[j]            -> sqForward.forwardData[j]
    2. uncacheForward.forwardMask[j] & isNCReplay
                                           -> uncacheForward.forwardData[j]
    3. sbufferForward.forwardMask[j]       -> sbufferForward.forwardData[j]
    4. mshrForward.forwardMask[j]          -> mshrForward.forwardData[j]
    5. tldForward.valid                    -> tldForward.forwardData[j]
    6. rawData[j] where rawData = (isNCReplay | isMMIOReplay)
                                  ? uncacheBypass.data : dcacheResp.data

Contract: docs/contracts/load-datapath.md
"""
from __future__ import annotations

import random

S1_META_FIELDS = {
    "bankOffset": 4,
    "fuOpType": 12,
    "fpWen": 1,
    "isNCReplay": 1,
    "isMMIOReplay": 1,
    "isUnalignHead": 1,
}
FORWARD_SOURCES = ("sq", "sbuffer", "uncache", "mshr")
FORWARD_PORT_NAMES = {"sq": "Sq", "sbuffer": "Sbuffer", "uncache": "Uncache",
                      "mshr": "MSHR"}

# fuOpType -> (zero-extend width, is_nan_boxed)
EXT_TYPES = {
    0x10: (1, False), 0x50: (1, False),          # LBU, HLV.BU
    0x12: (2, False), 0x52: (2, False), 0x72: (2, False),   # LHU, HLV.HU ...
    0x14: (4, False), 0x54: (4, False), 0x74: (4, False),   # LWU, HLV.WU ...
    0x06: (8, False), 0x46: (8, False),          # LD
    0x00: (1, False), 0x40: (1, False),          # LB (sign)
    0x02: (2, False), 0x42: (2, False),          # LH (sign)
    0x04: (4, False), 0x44: (4, False),          # LW (sign)
}
SIGNED_TYPES = {0x00, 0x40, 0x02, 0x42, 0x04, 0x44}
FP16_TYPES = {0x02}          # LH_FP when fpWen
FP32_TYPES = {0x04}          # LW_FP when fpWen


def byte(payload: int, index: int) -> int:
    return (payload >> (8 * index)) & 0xFF


def shift_right_bytes(data: int, offset: int) -> int:
    """Logical right shift by ``offset`` bytes, zero-filled at the top.

    This is what ``s3ShiftHead`` actually builds: ``result = data >> 8*offset``
    with the vacated high bytes cleared (the byte at position ``i`` becomes the
    old byte ``i + offset``, and bytes past 15 vanish). The top byte is only
    filled by the ``offset=15`` term, which is exactly ``data >> 120``.
    """
    return (data >> (8 * offset)) & ((1 << 128) - 1)


def extend_value(shifted: int, fu_op_type: int, fp_wen: int) -> int:
    """64-bit result put in the low half of the 128-bit output."""
    if fu_op_type in FP16_TYPES and fp_wen:
        return (0xFFFF_FFFF_FFFF << 16) | (shifted & 0xFFFF)
    if fu_op_type in FP32_TYPES and fp_wen:
        return (0xFFFF_FFFF << 32) | (shifted & 0xFFFF_FFFF)
    width = None
    for fu_type, (bits, _nan) in EXT_TYPES.items():
        if fu_type == fu_op_type:
            width = bits
            break
    if width is None:
        return 0
    value = shifted & ((1 << (8 * width)) - 1)
    if fu_op_type in SIGNED_TYPES:
        sign = 1 << (8 * width - 1)
        if value & sign:
            value -= (1 << (8 * width))
        value &= (1 << 64) - 1
    return value


class DataPathState:
    __slots__ = ("s2_valid", "s2_meta", "is_unalign_tail", "unalign_head_offset",
                 "s3_valid", "s3_data", "s3_is_tail", "s3_oh", "s3_sel",
                 "s3_tail_sel", "s4_shift_head")

    def __init__(self) -> None:
        self.s2_valid = 0
        self.s2_meta = {name: 0 for name in S1_META_FIELDS}
        self.is_unalign_tail = 0
        self.unalign_head_offset = 0
        self.s3_valid = 0
        self.s3_data = 0
        self.s3_is_tail = 0
        self.s3_oh = 0
        self.s3_sel = 0
        self.s3_tail_sel = 0
        self.s4_shift_head = 0


def s2_raw_data(meta: dict, bypass: int, dcache: int) -> int:
    if meta["isNCReplay"] or meta["isMMIOReplay"]:
        return bypass
    return dcache


def merge_bytes(meta: dict, forward: dict, tld_valid: int, tld_data: list[int],
                bypass: int, dcache: int) -> int:
    raw = s2_raw_data(meta, bypass, dcache)
    result = 0
    for index in range(16):
        value = byte(raw, index)
        if forward["sq"]["mask"][index]:
            value = forward["sq"]["data"][index]
        elif forward["uncache"]["mask"][index] and meta["isNCReplay"]:
            value = forward["uncache"]["data"][index]
        elif forward["sbuffer"]["mask"][index]:
            value = forward["sbuffer"]["data"][index]
        elif forward["mshr"]["mask"][index]:
            value = forward["mshr"]["data"][index]
        elif tld_valid:
            value = tld_data[index]
        result |= value << (8 * index)
    return result


def rdata_type_oh(meta: dict) -> int:
    fu = meta["fuOpType"]
    fp = meta["fpWen"]
    bits = [0] * 9
    bits[0] = 1 if fu in (0x10, 0x50) else 0
    bits[1] = 1 if fu in (0x12, 0x52, 0x72) else 0
    bits[2] = 1 if fu in (0x14, 0x54, 0x74) else 0
    bits[3] = 1 if fu in (0x06, 0x46) else 0
    bits[4] = 1 if fu in (0x00, 0x40) else 0
    bits[5] = 1 if ((fu == 0x02 and not fp) or fu == 0x42) else 0
    bits[6] = 1 if ((fu == 0x04 and not fp) or fu == 0x44) else 0
    bits[7] = 1 if (fu == 0x02 and fp) else 0
    bits[8] = 1 if (fu == 0x04 and fp) else 0
    value = 0
    for index, bit in enumerate(bits):
        value |= bit << index
    return value


def tail_select(head_offset: int) -> int:
    """One-hot over the 15 possible non-zero head offsets."""
    value = 0
    for shift in range(1, 16):
        offset = 16 - shift
        if head_offset == offset:
            value |= 1 << (shift - 1)
    return value


class LoadDataPathModel:
    def __init__(self) -> None:
        self.state = DataPathState()

    def reset(self) -> None:
        self.state = DataPathState()

    def cycle(self, s1_valid: int, s1_meta: dict, forward: dict, tld_valid: int,
              tld_data: list[int], bypass: int, dcache: int) -> dict:
        pre = self.state
        # ---- pre-edge derived values ----------------------------------------
        head_hit = bool(pre.s2_meta["isUnalignHead"]) and bool(pre.s2_valid)
        if pre.s2_valid:
            merged = merge_bytes(pre.s2_meta, forward, tld_valid, tld_data,
                                 bypass, dcache)
            oh = rdata_type_oh(pre.s2_meta)
            sel = 1 << (pre.s2_meta["bankOffset"] & 0xF)
        else:
            merged, oh, sel = None, None, None

        # ---- the edge --------------------------------------------------------
        state = DataPathState()
        state.s2_valid = 1 if s1_valid else 0
        state.s2_meta = {name: (s1_meta[name] if s1_valid else pre.s2_meta[name])
                         for name in S1_META_FIELDS}
        state.is_unalign_tail = 1 if head_hit else 0
        state.unalign_head_offset = (pre.s2_meta["bankOffset"] if head_hit
                                     else pre.unalign_head_offset)
        state.s3_valid = pre.s2_valid
        if pre.s2_valid:
            state.s3_data = merged
            state.s3_is_tail = pre.is_unalign_tail
            state.s3_oh = oh
            state.s3_sel = sel
            state.s3_tail_sel = tail_select(pre.unalign_head_offset)
        else:
            # Payload registers hold their previous value when the stage is empty.
            state.s3_data = pre.s3_data
            state.s3_is_tail = pre.s3_is_tail
            state.s3_oh = pre.s3_oh
            state.s3_sel = pre.s3_sel
            state.s3_tail_sel = pre.s3_tail_sel
        if pre.s3_valid:
            rotated = shift_right_bytes(pre.s3_data, _one_hot_index(pre.s3_sel))
            state.s4_shift_head = rotated
        else:
            state.s4_shift_head = pre.s4_shift_head
        self.state = state

        # ---- post-edge combinational outputs (from the new state) -----------
        rotated_next = shift_right_bytes(state.s3_data,
                                          _one_hot_index(state.s3_sel))
        if state.s3_is_tail:
            merged_tail = state.s4_shift_head
            for shift in range(1, 16):
                if state.s3_tail_sel & (1 << (shift - 1)):
                    merged_tail |= (state.s3_data << (8 * shift)) & ((1 << 128) - 1)
            shift_data = merged_tail
        else:
            shift_data = rotated_next
        extended = extend_value(shift_data, _oh_to_fuop(state.s3_oh, state),
                                _oh_fp(state.s3_oh, state))
        return {
            "s3_valid": state.s3_valid,
            "s2_valid": state.s2_valid,
            "shift_data": shift_data,
            "shift_and_ext": extended,
            "state": state,
        }


def _one_hot_index(sel: int) -> int:
    for index in range(16):
        if sel & (1 << index):
            return index
    return 0


# The OH is captured from the *pre-edge* metadata, so the extension input type
# must be recovered from the decoded one-hot itself rather than from s2_meta.
OH_TO_FUOP = {
    0: 0x10, 1: 0x12, 2: 0x14, 3: 0x06, 4: 0x00,
    5: 0x02, 6: 0x04, 7: 0x02, 8: 0x04,
}
OH_FP = {7: 1, 8: 1}


def _oh_to_fuop(oh: int, state) -> int:
    for index, value in OH_TO_FUOP.items():
        if oh & (1 << index):
            return value
    return 0xFFFF


def _oh_fp(oh: int, state) -> int:
    for index, value in OH_FP.items():
        if oh & (1 << index):
            return value
    return 0


class LoadDataPathEnv:
    def __init__(self, dut, coverage=None) -> None:
        self.dut = dut
        self.coverage = coverage
        self.s1_valid = dut.io_s1Meta_valid
        self.s1_meta = {name: getattr(dut, f"io_s1Meta_bits_{name}")
                        for name in S1_META_FIELDS}
        self.forward = {}
        for source in FORWARD_SOURCES:
            port = FORWARD_PORT_NAMES[source]
            self.forward[source] = {
                "mask": [getattr(dut, f"io_s2{port}ForwardResp_bits_forwardMask_{i}")
                         for i in range(16)],
                "data": [getattr(dut, f"io_s2{port}ForwardResp_bits_forwardData_{i}")
                         for i in range(16)],
            }
        self.tld_valid = dut.io_s2TLDForwardResp_valid
        self.tld_data = [getattr(dut, f"io_s2TLDForwardResp_bits_forwardData_{i}")
                         for i in range(16)]
        self.bypass = dut.io_s2UncacheBypassResp_bits_data
        self.dcache = dut.io_s2DCacheResp_bits_data
        self.out_shift = dut.io_s3ShiftData
        self.out_ext = dut.io_s3ShiftAndExtData
        self.model = LoadDataPathModel()
        self.cycles = 0

    def reset(self, cycles: int = 3) -> None:
        self.dut.reset.Set(1)
        for _ in range(cycles):
            self.dut.Step(1)
        self.dut.reset.Set(0)
        self.model.reset()
        self.drive(0, {name: 0 for name in S1_META_FIELDS},
                   {source: {"mask": [0] * 16, "data": [0] * 16}
                    for source in FORWARD_SOURCES}, 0, [0] * 16, 0, 0)
        self.dut.Step(1)

    def drive(self, s1_valid: int, s1_meta: dict, forward: dict, tld_valid: int,
              tld_data: list[int], bypass: int, dcache: int) -> None:
        self.s1_valid.Set(1 if s1_valid else 0)
        for name, signal in self.s1_meta.items():
            signal.Set(int(s1_meta.get(name, 0)))
        for source in FORWARD_SOURCES:
            for index in range(16):
                self.forward[source]["mask"][index].Set(
                    1 if forward[source]["mask"][index] else 0)
                self.forward[source]["data"][index].Set(
                    int(forward[source]["data"][index]) & 0xFF)
        self.tld_valid.Set(1 if tld_valid else 0)
        for index in range(16):
            self.tld_data[index].Set(int(tld_data[index]) & 0xFF)
        self.bypass.Set(int(bypass) & ((1 << 128) - 1))
        self.dcache.Set(int(dcache) & ((1 << 128) - 1))

    def cycle(self, s1_valid: int, s1_meta: dict, forward: dict, tld_valid: int,
              tld_data: list[int], bypass: int, dcache: int,
              context: str = "cycle") -> dict:
        want = self.model.cycle(s1_valid, s1_meta, forward, tld_valid, tld_data,
                                bypass, dcache)
        self.drive(s1_valid, s1_meta, forward, tld_valid, tld_data, bypass, dcache)
        self.dut.Step(1)
        got_shift = int(self.out_shift.value)
        got_ext = int(self.out_ext.value)
        if want["s3_valid"]:
            if got_shift != want["shift_data"]:
                raise AssertionError(
                    f"{context}: s3ShiftData {got_shift:#034x} != "
                    f"{want['shift_data']:#034x} (s1_valid={s1_valid} "
                    f"meta={s1_meta} tld={tld_valid})")
            if got_ext != want["shift_and_ext"]:
                raise AssertionError(
                    f"{context}: s3ShiftAndExtData {got_ext:#018x} != "
                    f"{want['shift_and_ext']:#018x} (meta={s1_meta})")
        if self.coverage is not None:
            self.coverage.observe(want=want, meta=s1_meta, tld_valid=tld_valid)
        self.cycles += 1
        return want


def blank_forward() -> dict:
    return {source: {"mask": [0] * 16, "data": [0] * 16}
            for source in FORWARD_SOURCES}


def random_forward(rng: random.Random, density: float = 0.2) -> dict:
    return {source: {"mask": [1 if rng.random() < density else 0 for _ in range(16)],
                     "data": [rng.randrange(256) for _ in range(16)]}
            for source in FORWARD_SOURCES}
