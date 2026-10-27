"""MainPipe UT: store/atomic main pipeline, refill install, probe release."""
from __future__ import annotations

import pytest

from dcacheverify.main_pipe.coverage import MainPipeCoverage
from dcacheverify.load_pipe.model import dcache_index
from dcacheverify.miss_queue.env import dcache_alias
from dcacheverify.main_pipe.env import (
    BRANCH,
    BTON,
    BTOB,
    DIRTY,
    M_PFR,
    M_XA_ADD,
    M_XA_CASD,
    M_XA_CASQ,
    M_XA_SWAP,
    M_XLR,
    M_XSC,
    M_XRD,
    M_XWR,
    NOTHING,
    NTON,
    PREFETCH_SOURCE,
    STORE_SOURCE,
    TTOB,
    TTON,
    TTOT,
    TRUNK,
    MainPipeEnv,
    block_addr,
    default_banks,
    dcache_index,
    line_from_banks,
    merge_line,
    phy_tag,
)


@pytest.fixture
def mp(dut_factory):
    dut = dut_factory("main_pipe")
    env = MainPipeEnv(dut, MainPipeCoverage())
    env.reset()
    return env


def first(snapshots, key):
    for snap in snapshots:
        if snap[key]:
            return snap
    return None


def all_writes(snapshots, key):
    return [snap for snap in snapshots if snap[key]]


# MP-FP-001 / MP-FP-002 / MP-FP-012
def test_store_hit_writes_merged_line(mp):
    banks = default_banks()
    result = mp.store_op(vaddr=0x1040, paddr=0x8040, data=0x1122334455667788,
                         mask=0xFF, store_id=11, coh=DIRTY, hit_way=2,
                         banks=banks)
    snaps = result["snapshots"]
    assert result["outcome"] == "hit"
    read = first([result["s0"], *snaps], "tag_read")
    assert read is not None and read["tag_read_idx"] == dcache_index(0x1040)
    assert read["meta_read_idx"] == dcache_index(0x1040)
    assert first(snaps, "readline") is None
    write = first(snaps, "data_write")
    assert write is not None
    assert write["data_wmask"] == 0xF
    assert write["data_values"] == result["expected_line"]
    hit = first(snaps, "store_hit")
    assert hit is not None and hit["store_hit_id"] == 11
    assert hit["tag_write"] == 0
    assert hit["meta_write"] == 0
    assert hit["access_flag"] == 1 and hit["access_flag_value"] == 1
    assert hit["access_flag_way"] == 1 << 2
    assert write["data_write"] != 0
    assert not any(snap["miss_req"] for snap in snaps)


# MP-FP-002
def test_store_partial_bank_reads_line_and_merges_bytes(mp):
    banks = default_banks()
    result = mp.store_op(vaddr=0x1080, paddr=0x9080, data=0xAB, mask=0x01,
                         store_id=4, coh=DIRTY, hit_way=0, banks=banks)
    snaps = result["snapshots"]
    readline = first([result["s0"], *snaps], "readline")
    assert readline is not None
    assert readline["readline_rmask"] == 0x1
    assert readline["readline_way"] == 0x1
    write = first(snaps, "data_write")
    assert write["data_wmask"] == 0x1
    assert write["data_values"][0] == ((banks[0] & 0xFF00) | 0xAB)
    assert write["data_values"][1:] == banks[1:]
    assert result["outcome"] == "hit"


# MP-FP-001 / MP-FP-002 / MP-FP-007
def test_store_trunk_to_dirty_updates_meta(mp):
    banks = default_banks(0x200)
    data = (0x99887766 << 64) | 0x1122334455667788
    result = mp.store_op(vaddr=0x2000, paddr=0xA000, data=data,
                         mask=0x0F00, store_id=7, coh=TRUNK, hit_way=1,
                         banks=banks)
    snaps = result["snapshots"]
    write = first(snaps, "data_write")
    assert write["data_wmask"] == 0x30
    assert write["data_values"] == result["expected_line"]
    assert result["expected_line"][4] == 0x7766
    assert result["expected_line"][5] == 0x9988
    meta = first(snaps, "meta_write")
    assert meta is not None
    assert meta["meta_write_idx"] == dcache_index(0x2000)
    assert meta["meta_write_way"] == 1 << 1
    assert meta["meta_write_coh"] == DIRTY
    hit = first(snaps, "store_hit")
    assert hit is not None and hit["access_flag_way"] == 1 << 1


# MP-FP-002
def test_store_full_line_overwrite_skips_line_read(mp):
    line = 0
    for bank in range(32):
        line |= ((0x3000 + bank * 3) & 0xFFFF) << (16 * bank)
    result = mp.store_op(vaddr=0x3000, paddr=0xB000, data=line,
                         mask=(1 << 64) - 1, store_id=2, coh=DIRTY, hit_way=3)
    snaps = result["snapshots"]
    assert first([result["s0"], *snaps], "readline") is None
    write = first(snaps, "data_write")
    assert write["data_wmask"] == 0xFFFFFFFF
    assert write["data_values"] == [((line >> (16 * bank)) & 0xFFFF)
                                   for bank in range(32)]
    hit = first(snaps, "store_hit")
    assert hit["access_flag_way"] == 1 << 3


# MP-FP-003
def test_store_miss_request_fields(mp):
    data = 0xCAFEBABE12345678 | (0xAB << (16 * 20))
    result = mp.store_op(vaddr=0x2400, paddr=0xC000, data=data, mask=0xFFFF,
                         store_id=5, coh=NOTHING, tag_match=False)
    snaps = result["snapshots"]
    miss = first(snaps, "miss_req")
    assert miss is not None
    assert miss["miss_addr"] == block_addr(0xC000) == 0xC000
    assert miss["miss_vaddr"] == 0x2400
    assert miss["miss_store_data"] == data
    assert miss["miss_store_mask"] == 0xFFFF
    assert miss["miss_source"] == STORE_SOURCE
    assert miss["miss_cmd"] == M_XWR
    assert miss["miss_id"] == 5
    assert miss["miss_full_overwrite"] == 0
    assert miss["miss_ready"] == 1
    hit = first(snaps, "store_hit")
    assert hit is not None
    assert hit["store_hit_id"] == 5
    assert not any(snap["data_write"] for snap in snaps)


# MP-FP-003
def test_store_partial_mask_miss(mp):
    result = mp.store_op(vaddr=0x2480, paddr=0xC080, data=0x42, mask=0x80,
                         store_id=8, coh=NOTHING, tag_match=False)
    snaps = result["snapshots"]
    miss = first(snaps, "miss_req")
    assert miss is not None
    assert miss["miss_store_mask"] == 0x80
    assert miss["miss_store_data"] == 0x42
    assert miss["miss_full_overwrite"] == 0
    assert result["outcome"] == "miss_accepted"


# MP-FP-003
def test_store_full_line_miss_marks_full_overwrite(mp):
    line = 0
    for bank in range(32):
        line |= ((0x7000 + bank) & 0xFFFF) << (16 * bank)
    result = mp.store_op(vaddr=0x2500, paddr=0xC100, data=line,
                         mask=(1 << 64) - 1, store_id=6, coh=NOTHING,
                         tag_match=False)
    miss = first(result["snapshots"], "miss_req")
    assert miss is not None
    assert miss["miss_full_overwrite"] == 1
    assert miss["miss_store_data"] == line


# MP-FP-004
def test_store_replay_when_miss_queue_backpressures(mp):
    result = mp.store_op(vaddr=0x2600, paddr=0xC200, data=0x1234, mask=0xFF,
                         store_id=9, coh=NOTHING, tag_match=False,
                         miss_ready=False)
    snaps = result["snapshots"]
    assert result["outcome"] == "replay"
    replay = first(snaps, "store_replay")
    assert replay is not None
    assert replay["store_replay_id"] == 9
    assert first(snaps, "store_hit") is None
    miss = first(snaps, "miss_req")
    assert miss is not None and miss["miss_ready"] == 0


# MP-FP-005
def test_amo_swap_returns_old_value_and_writes_new(mp):
    banks = default_banks(0x400)
    amo_data = 0x0123456789ABCDEF
    result = mp.atomic_op(vaddr=0x4000, paddr=0xD000, cmd=M_XA_SWAP,
                          amo_data=amo_data, amo_mask=0xFFFF, word_idx=0,
                          coh=DIRTY, hit_way=0, banks=banks)
    snaps = result["snapshots"]
    assert result["outcome"] == "hit"
    resp = first(snaps, "atomic_resp")
    assert resp is not None
    assert resp["atomic_data"] == line_from_banks(banks, 0, 8)
    assert resp["atomic_miss"] == 0 and resp["atomic_replay"] == 0
    write = first(snaps, "data_write")
    assert write is not None
    assert write["data_wmask"] == 0xF
    expected = list(banks)
    for offset in range(4):
        expected[offset] = (amo_data >> (16 * offset)) & 0xFFFF
    assert write["data_values"] == expected
    assert not any(snap["miss_req"] for snap in snaps)


# MP-FP-005
def test_amo_add_uses_sram_word_and_byte_mask(mp):
    banks = default_banks(0x500)
    result = mp.atomic_op(vaddr=0x4100, paddr=0xD100, cmd=M_XA_ADD,
                          amo_data=0x20, amo_mask=0x00FF, word_idx=1,
                          coh=DIRTY, hit_way=1, banks=banks)
    snaps = result["snapshots"]
    write = first(snaps, "data_write")
    assert write is not None
    assert write["data_wmask"] == 0xF0
    assert result["old_word"] == line_from_banks(banks, 4, 4)
    expected = list(banks)
    for offset in range(4):
        expected[4 + offset] = (result["expected_word"] >> (16 * offset)) & 0xFFFF
    assert write["data_values"] == expected
    resp = first(snaps, "atomic_resp")
    assert resp["atomic_data"] == line_from_banks(banks, 4, 8)

    # Partial byte mask: only the selected byte of the word changes.
    partial = mp.atomic_op(vaddr=0x4200, paddr=0xD200, cmd=M_XA_ADD,
                           amo_data=0x1122334455667788, amo_mask=0x1,
                           word_idx=0, coh=DIRTY, banks=banks)
    pwrite = first(partial["snapshots"], "data_write")
    assert pwrite["data_wmask"] == 0xF
    assert pwrite["data_values"][0] == (partial["expected_word"] & 0xFFFF)
    assert (pwrite["data_values"][0] & 0xFF00) == (banks[0] & 0xFF00)


# MP-FP-006
def test_amo_miss_request_and_replay(mp):
    # Use non-default word_idx / amo_cmp / vaddr so a pass-through bug cannot hide
    # behind an all-zero field.
    vaddr = 0x4A40
    result = mp.atomic_op(vaddr=vaddr, paddr=0xD300, cmd=M_XA_SWAP,
                          amo_data=0xDEAD, amo_mask=0xFFFF, word_idx=2,
                          amo_cmp=0x1234, coh=NOTHING, tag_match=False)
    snaps = result["snapshots"]
    miss = first(snaps, "miss_req")
    assert miss is not None
    assert miss["miss_addr"] == block_addr(0xD300)
    assert miss["miss_vaddr"] == vaddr
    assert miss["miss_amo_data"] == 0xDEAD
    assert miss["miss_amo_mask"] == 0xFFFF
    assert miss["miss_cmd"] == M_XA_SWAP
    # Fields that route the AMO replay to the right word and compare value.
    assert miss["miss_word_idx"] == 2, miss
    assert miss["miss_amo_cmp"] == 0x1234, miss
    # Alias/set are the DCache index functions of the virtual address, and the
    # requested coherence is the observed line state (NOTHING for a miss).
    assert miss["miss_vaddr_alias"] == dcache_alias(vaddr), miss
    assert miss["miss_vaddr_set"] == dcache_index(vaddr), miss
    assert miss["miss_req_coh"] == NOTHING, miss
    # The acknowledgement of a miss goes back to the LSU only when the
    # MissQueue returns the refill (also observed by the DCache top test).
    assert first(snaps, "atomic_resp") is None
    assert not any(snap["data_write"] for snap in snaps)

    replay = mp.atomic_op(vaddr=0x4300, paddr=0xD300, cmd=M_XA_SWAP,
                          amo_data=0xDEAD, amo_mask=0xFFFF, word_idx=0,
                          coh=NOTHING, tag_match=False, miss_ready=False)
    rsnaps = replay["snapshots"]
    assert replay["outcome"] == "miss_replay"
    rresp = first(rsnaps, "atomic_resp")
    assert rresp is not None
    assert rresp["atomic_miss"] == 1 and rresp["atomic_replay"] == 1


# MP-FP-006
def test_amo_add_miss_request(mp):
    result = mp.atomic_op(vaddr=0x4380, paddr=0xD380, cmd=M_XA_ADD,
                          amo_data=0x20, amo_mask=0xFF, word_idx=2,
                          coh=NOTHING, tag_match=False)
    snaps = result["snapshots"]
    assert result["outcome"] == "miss"
    miss = first(snaps, "miss_req")
    assert miss is not None
    assert miss["miss_cmd"] == M_XA_ADD
    assert miss["miss_amo_data"] == 0x20
    assert miss["miss_amo_mask"] == 0xFF
    assert miss["miss_addr"] == block_addr(0xD380)


# MP-FP-006 / MP-FP-009
def test_amo_miss_completed_by_refill(mp):
    line = 0
    for bank in range(32):
        line |= ((0x8000 + bank) & 0xFFFF) << (16 * bank)
    result = mp.refill_op(vaddr=0x4400, paddr=0xD400, cmd=M_XA_SWAP,
                          miss_id=2, source=2, line_data=line,
                          amo_data=0xDEAD, amo_mask=0xFFFF, word_idx=0,
                          replace_way=1)
    snaps = result["snapshots"]
    resp = first(snaps, "atomic_resp")
    assert resp is not None
    assert resp["atomic_data"] == line_from_banks(
        [((line >> (16 * bank)) & 0xFFFF) for bank in range(32)], 0, 8)
    assert resp["atomic_miss"] == 0
    assert resp["atomic_ack_mq"] == 1
    write = first(snaps, "data_write")
    assert write is not None
    assert write["data_wmask"] == 0xFFFFFFFF
    assert write["data_values"][0] == 0xDEAD
    assert write["data_values"][1:4] == [0, 0, 0]
    assert write["data_values"][4:] == [
        (line >> (16 * bank)) & 0xFFFF for bank in range(4, 32)]
    meta = first(snaps, "meta_write")
    assert meta is not None and meta["meta_write_coh"] == DIRTY
    tag = first(snaps, "tag_write")
    assert tag is not None and tag["tag_write_way"] == 1 << 1


# MP-FP-007
def test_probe_shrink_dirty_line(mp):
    banks = default_banks(0x600)
    cases = [
        (0, TTOT, TRUNK, "trunk"),
        (1, TTOB, BRANCH, "branch"),
        (2, TTON, NOTHING, "nothing"),
    ]
    for param, wb_param, new_coh, name in cases:
        result = mp.probe_op(vaddr=0x5000, paddr=0xE000, param=param,
                             need_data=True, banks=banks, coh=DIRTY,
                             hit_way=1, probe_id=3)
        wb = first(result["snapshots"], "wb")
        assert wb is not None, name
        assert wb["wb_param"] == wb_param, name
        assert wb["wb_hasdata"] == 1, name
        assert wb["wb_voluntary"] == 0, name
        assert wb["wb_addr"] == block_addr(0xE000), name
        assert wb["wb_data"] == line_from_banks(banks), name
        assert wb["wb_corrupt"] == 0, name
        meta = first(result["snapshots"], "meta_write")
        assert meta is not None, name
        assert meta["meta_write_coh"] == new_coh, name
        assert meta["meta_write_way"] == 1 << 1, name
        assert meta["meta_write_idx"] == dcache_index(0x5000), name
        assert not any(snap["miss_req"] for snap in result["snapshots"])


# MP-FP-007
def test_probe_clean_line_and_need_data(mp):
    banks = default_banks(0x700)
    # toT on a Trunk line: permission unchanged, no data, no meta write.
    result = mp.probe_op(vaddr=0x5100, paddr=0xE100, param=0, need_data=False,
                         coh=TRUNK, hit_way=0, banks=banks)
    wb = first(result["snapshots"], "wb")
    assert wb["wb_param"] == TTOT
    assert wb["wb_hasdata"] == 0
    assert first(result["snapshots"], "meta_write") is None

    # toB on a Trunk line: downgrade to Branch, clean release without data.
    result = mp.probe_op(vaddr=0x5100, paddr=0xE100, param=1, need_data=False,
                         coh=TRUNK, hit_way=0, banks=banks)
    wb = first(result["snapshots"], "wb")
    assert wb["wb_param"] == TTOB and wb["wb_hasdata"] == 0
    meta = first(result["snapshots"], "meta_write")
    assert meta["meta_write_coh"] == BRANCH

    # Probe explicitly asks for data: clean line still releases data.
    result = mp.probe_op(vaddr=0x5100, paddr=0xE100, param=1, need_data=True,
                         coh=TRUNK, hit_way=0, banks=banks)
    wb = first(result["snapshots"], "wb")
    assert wb["wb_hasdata"] == 1 and wb["wb_data"] == line_from_banks(banks)

    # toB on a Branch line is a report (BtoB) with no meta update.
    result = mp.probe_op(vaddr=0x5100, paddr=0xE100, param=1, need_data=False,
                         coh=BRANCH, hit_way=0, banks=banks)
    wb = first(result["snapshots"], "wb")
    assert wb["wb_param"] == BTOB and wb["wb_hasdata"] == 0
    assert first(result["snapshots"], "meta_write") is None


# MP-FP-007
def test_probe_ton_on_branch_reports_bton(mp):
    # toN on a Branch line cedes to Nothing with a BtoN release.
    result = mp.probe_op(vaddr=0x5300, paddr=0xE300, param=2, need_data=False,
                         coh=BRANCH, hit_way=2, banks=default_banks(0x900))
    wb = first(result["snapshots"], "wb")
    assert wb is not None
    assert wb["wb_param"] == BTON
    assert wb["wb_hasdata"] == 0
    meta = first(result["snapshots"], "meta_write")
    assert meta is not None and meta["meta_write_coh"] == NOTHING
    assert meta["meta_write_way"] == 1 << 2


# MP-FP-008
def test_probe_miss_reports_ntoN(mp):
    for param in (1, 2):
        result = mp.probe_op(vaddr=0x5200, paddr=0xE200, param=param,
                             need_data=True, coh=DIRTY, tag_match=False,
                             replace_way=2)
        wb = first(result["snapshots"], "wb")
        assert wb is not None
        assert wb["wb_param"] == NTON
        assert wb["wb_hasdata"] == 0
        assert first(result["snapshots"], "meta_write") is None


# MP-FP-009 / MP-FP-012
def test_refill_load_and_store_install(mp):
    for cmd, way, new_coh in ((M_XRD, 1, TRUNK), (M_XWR, 2, DIRTY)):
        line = 0
        for bank in range(32):
            line |= ((0x5A00 + bank + way) & 0xFFFF) << (16 * bank)
        result = mp.refill_op(vaddr=0x6000, paddr=0xF000, cmd=cmd,
                              miss_id=3, source=2, line_data=line,
                              replace_way=way, pf_source=0)
        snaps = result["snapshots"]
        tag = first(snaps, "tag_write")
        assert tag is not None
        assert (tag["tag_write_tag"] & ((1 << 36) - 1)) == phy_tag(0xF000)
        assert tag["tag_write_way"] == 1 << way
        assert tag["tag_write_idx"] == dcache_index(0x6000)
        assert tag["tag_write_intend"] == 1
        write = first(snaps, "data_write")
        assert write is not None
        assert write["data_wmask"] == 0xFFFFFFFF
        assert write["data_values"] == result["expected_data"]
        meta = first(snaps, "meta_write")
        assert meta is not None
        assert meta["meta_write_coh"] == new_coh
        assert meta["meta_write_way"] == 1 << way
        resp = first(snaps, "s3_refill_resp")
        assert resp is not None
        err = first(snaps, "error_flag")
        assert err is not None
        assert err["error_flag_denied"] == 0 and err["error_flag_corrupt"] == 0
        assert err["error_flag_way"] == 1 << way
        acc = first(snaps, "access_flag")
        assert acc is not None and acc["access_flag_value"] == 1
        assert acc["access_flag_way"] == 1 << way
        repl = first([result["s0"], *snaps], "replace_access")
        assert repl is not None
        assert repl["replace_access_set"] == dcache_index(0x6000)
        assert repl["replace_access_way"] == way
        assert not any(snap["miss_req"] for snap in snaps)



# MP-FP-009 / MP-FP-011
def test_refill_with_prefetch_source_sets_flags(mp):
    line = 0x0123456789ABCDEF
    result = mp.refill_op(vaddr=0x6100, paddr=0xF100, cmd=M_XRD,
                          replace_way=0, pf_source=5, access=1,
                          line_data=line)
    snaps = result["snapshots"]
    pref = first(snaps, "prefetch_flag")
    assert pref is not None
    assert pref["prefetch_flag_source"] == 5
    acc = first(snaps, "access_flag")
    assert acc["access_flag"] == 1 and acc["access_flag_value"] == 1
    tag = first(snaps, "tag_write")
    assert (tag["tag_write_tag"] & ((1 << 36) - 1)) == phy_tag(0xF100)


# MP-FP-010 / MP-FP-012
def test_refill_error_marks(mp):
    for index, (denied, corrupt) in enumerate(((True, False), (False, True))):
        result = mp.refill_op(vaddr=0x6200 + index * 0x100,
                              paddr=0xF200 + index * 0x100, cmd=M_XRD,
                              replace_way=1 + index * 2,
                              denied=denied, corrupt=corrupt)
        snaps = result["snapshots"]
        err = first(snaps, "error_flag")
        assert err is not None
        assert err["error_flag_denied"] == (1 if denied else 0)
        assert err["error_flag_corrupt"] == (1 if corrupt else 0)
        ioerr = first(snaps, "error_valid")
        assert ioerr is not None
        assert ioerr["error_report"] == 0
        meta = first(snaps, "meta_write")
        assert meta is not None


# MP-FP-011
def test_prefetch_hit_and_miss(mp):
    banks = default_banks(0x800)
    for source in range(8):
        hit = mp.prefetch_op(vaddr=0x7000 + source * 0x40,
                             paddr=0x9000 + source * 0x40, source=source,
                             coh=DIRTY, hit_way=0, banks=banks)
        hsnaps = hit["snapshots"]
        acc = first(hsnaps, "access_flag")
        assert acc is not None and acc["access_flag_value"] == 1
        assert acc["access_flag_way"] == 1
        assert first(hsnaps, "miss_req") is None
        assert not any(snap["tag_write"] for snap in hsnaps)

    miss = mp.prefetch_op(vaddr=0x7000, paddr=0x9000, source=5, coh=NOTHING,
                          tag_match=False)
    msnaps = miss["snapshots"]
    mreq = first(msnaps, "miss_req")
    assert mreq is not None
    assert mreq["miss_source"] == PREFETCH_SOURCE
    assert mreq["miss_pf_source"] == 5
    assert mreq["miss_cmd"] == M_PFR
    assert mreq["miss_addr"] == block_addr(0x9000)
    assert mreq["miss_vaddr"] == 0x7000


# MP-FP-012
def test_address_index_and_way_selection(mp):
    # One address per set class (index 0, a low set, a high set, set 255) x
    # all four ways: the tag/meta index and the way_en one-hot must agree.
    addresses = [
        (0x0000, 0x0000, "zero"),
        (0x0540, 0x0540, "low"),
        (0x1000, 0x1000, "high_set_start"),
        (0x3FC0, 0x3FC0, "max"),
    ]
    indices = set()
    for vaddr, paddr, name in addresses:
        for way in range(4):
            result = mp.store_op(vaddr=vaddr, paddr=paddr, data=0xA5A5,
                                 mask=0xFF, store_id=way, coh=TRUNK,
                                 hit_way=way)
            snaps = result["snapshots"]
            assert result["index"] == dcache_index(vaddr)
            assert any(snap["tag_read_idx"] == result["index"]
                       for snap in [result["s0"], *snaps])
            meta = first(snaps, "meta_write")
            assert meta is not None
            assert meta["meta_write_idx"] == result["index"]
            assert meta["meta_write_way"] == 1 << way
            hit = first(snaps, "store_hit")
            assert hit["access_flag_way"] == 1 << way
            indices.add(result["index"])
    assert indices == {0, 21, 64, 255}


# MP-FP-003
def test_store_miss_with_word_mask(mp):
    result = mp.store_op(vaddr=0x2700, paddr=0xC300, data=0x0123456789ABCDEF,
                         mask=0xFF, store_id=12, coh=NOTHING,
                         tag_match=False)
    miss = first(result["snapshots"], "miss_req")
    assert miss is not None
    assert miss["miss_store_mask"] == 0xFF
    assert result["outcome"] == "miss_accepted"


# MP-FP-004
def test_store_replay_keeps_mask_shape(mp):
    line = 0
    for bank in range(32):
        line |= (0xC0DE + bank) << (16 * bank) & 0xFFFFFFFFFFFFFFFF
    for mask, data in (((1 << 64) - 1, line), (0x0F00, 0x99887766)):
        result = mp.store_op(vaddr=0x2800, paddr=0xC400, data=data, mask=mask,
                             store_id=13, coh=NOTHING, tag_match=False,
                             miss_ready=False)
        assert result["outcome"] == "replay"
        replay = first(result["snapshots"], "store_replay")
        assert replay is not None and replay["store_replay_id"] == 13
        miss = first(result["snapshots"], "miss_req")
        assert miss is not None and miss["miss_store_mask"] == mask


# MP-FP-006
def test_amo_add_miss_replay(mp):
    result = mp.atomic_op(vaddr=0x4390, paddr=0xD390, cmd=M_XA_ADD,
                          amo_data=0x20, amo_mask=0xFF, word_idx=0,
                          coh=NOTHING, tag_match=False, miss_ready=False)
    snaps = result["snapshots"]
    assert result["outcome"] == "miss_replay"
    resp = first(snaps, "atomic_resp")
    assert resp is not None and resp["atomic_replay"] == 1


# MP-FP-009 / MP-FP-010 / MP-FP-012
def test_refill_way_and_error_matrix(mp):
    ways = {0: [], 1: [], 2: [], 3: []}
    for way in range(4):
        for denied, corrupt in ((False, False), (True, False), (False, True)):
            tag = 0x7000 + way * 0x100 + (0x10 if denied else 0x20 if corrupt else 0)
            result = mp.refill_op(
                vaddr=tag, paddr=tag | 0x800000,
                cmd=M_XRD, replace_way=way, denied=denied, corrupt=corrupt)
            snaps = result["snapshots"]
            tag_write = first(snaps, "tag_write")
            assert tag_write["tag_write_way"] == 1 << way
            assert tag_write["tag_write_idx"] == dcache_index(tag)
            err = first(snaps, "error_flag")
            assert err["error_flag_way"] == 1 << way
            assert err["error_flag_denied"] == (1 if denied else 0)
            assert err["error_flag_corrupt"] == (1 if corrupt else 0)
            ways[way].append((denied, corrupt))
    assert all(len(items) == 3 for items in ways.values())


# MP-FP-009
def test_refill_victim_release(mp):
    victim_tag = 0x12345678
    # The Release address is the victim tag plus the low set offset of the
    # request vaddr (the hashed high set bits live in the tag itself).
    expected_addr = (victim_tag << 12) | (((0x6300 >> 6) & 0x3F) << 6)
    for coh, want_wb, want_param, want_data in (
            (DIRTY, True, TTON, 1),
            (TRUNK, True, TTON, 0),
            (BRANCH, True, BTON, 0),
            (NOTHING, False, None, None)):
        result = mp.refill_op(vaddr=0x6300, paddr=0xF300, cmd=M_XRD,
                              replace_way=1, replace_coh=coh)
        wb = first(result["snapshots"], "wb")
        if not want_wb:
            assert wb is None
            continue
        assert wb is not None
        assert wb["wb_param"] == want_param
        assert wb["wb_voluntary"] == 1
        assert wb["wb_hasdata"] == want_data
        assert wb["wb_addr"] == expected_addr
        assert wb["wb_corrupt"] == 0


# MP-FP-013
def test_lr_sc_reservation(mp):
    banks = default_banks(0x900)
    lr = mp.atomic_op(vaddr=0x8000 + 0x40, paddr=0xE000, cmd=M_XLR,
                      coh=DIRTY, hit_way=0, banks=banks)
    lsnaps = lr["snapshots"]
    resp = first(lsnaps, "atomic_resp")
    assert resp is not None and resp["atomic_data"] == line_from_banks(banks, 0, 8)
    assert resp["atomic_miss"] == 0
    assert not any(snap["data_write"] for snap in lsnaps)
    locked = first(lsnaps, "lrsc_valid")
    assert locked is not None
    assert locked["lrsc_block"] == block_addr(0xE000)
    assert any(snap["block_lr"] for snap in lsnaps)

    # SC in the same reservation window must write the masked word.
    sc = mp.atomic_op(vaddr=0x8000 + 0x40, paddr=0xE000, cmd=M_XSC,
                      amo_data=0x12345678, amo_mask=0x0F, coh=DIRTY,
                      hit_way=0, banks=banks)
    scsnaps = sc["snapshots"]
    write = first(scsnaps, "data_write")
    assert write is not None
    assert write["data_wmask"] == 0xF
    # SC writes the full 4-bank word; masked bytes take amo_data and the
    # remaining bytes of the word keep their SRAM value.
    assert write["data_values"][0] == 0x5678
    assert write["data_values"][1] == 0x1234
    assert write["data_values"][2:4] == banks[2:4]
    assert write["data_values"][4:] == banks[4:]
    scresp = first(scsnaps, "atomic_resp")
    assert scresp is not None
    assert not any(snap["lrsc_valid"] for snap in scsnaps[-2:])

    # SC without a reservation must not write.
    fail = mp.atomic_op(vaddr=0x8000 + 0x40, paddr=0xE000, cmd=M_XSC,
                        amo_data=0xFFFFFFFF, amo_mask=0xFF, coh=DIRTY,
                        hit_way=0, banks=banks, reservation="invalid")
    assert not any(snap["data_write"] for snap in fail["snapshots"])
    assert first(fail["snapshots"], "atomic_resp") is not None

    # invalid_resv_set clears the reservation established by LR.
    mp.atomic_op(vaddr=0x8000 + 0x40, paddr=0xE000, cmd=M_XLR,
                 coh=DIRTY, hit_way=0, banks=banks)
    cleared = mp.clear_reservation()
    assert not any(snap["lrsc_valid"] for snap in cleared)
    after = mp.atomic_op(vaddr=0x8000 + 0x40, paddr=0xE000, cmd=M_XSC,
                         amo_data=0xFFFFFFFF, amo_mask=0xFF, coh=DIRTY,
                         hit_way=0, banks=banks, reservation="cleared")
    assert not any(snap["data_write"] for snap in after["snapshots"])


# MP-FP-014
def test_amo_cas_widths(mp):
    banks = default_banks(0xB00)
    masks = {0x18: 0xFFFF, 0x1A: 0x0F, 0x1B: 0xFF, 0x1C: 0x03, 0x1D: 0x01}
    for cmd, mask in masks.items():
        if cmd == 0x18:
            for word_idx in (0, 2, 4, 6):
                base = (word_idx >> 1) * 8
                cmp = line_from_banks(banks, base, 8)
                data = int.from_bytes(bytes([0xEE] * 16), "little")
                result = mp.atomic_op(vaddr=0x9000, paddr=0xF000 + base,
                                      cmd=cmd, amo_data=data, amo_mask=mask,
                                      amo_cmp=cmp, word_idx=word_idx,
                                      coh=DIRTY, hit_way=0, banks=banks)
                assert result["cas_match"] is True
                write = first(result["snapshots"], "data_write")
                assert write is not None
                assert write["data_wmask"] == 0xFF << base
                assert write["data_values"][base:base + 8] == [0xEEEE] * 8
                assert write["data_values"][:base] == banks[:base]
                assert write["data_values"][base + 8:] == banks[base + 8:]
        else:
            width = {0x1A: 4, 0x1B: 8, 0x1C: 2, 0x1D: 1}[cmd]
            base = 0
            cmp = line_from_banks(banks, base, (width + 1) // 2) & ((1 << (8 * width)) - 1)
            data = 0xA1B2C3D4E5F60718
            result = mp.atomic_op(vaddr=0x9100, paddr=0xF100, cmd=cmd,
                                  amo_data=data, amo_mask=mask, amo_cmp=cmp,
                                  word_idx=0, coh=DIRTY, hit_way=1, banks=banks)
            assert result["cas_match"] is True
            write = first(result["snapshots"], "data_write")
            assert write is not None
            # Every non-Q CAS writes the 4-bank word that contains it; bytes
            # outside the compare width keep their SRAM value.
            assert write["data_wmask"] == 0xF
            expected = list(banks[:4])
            for byte in range(8):
                if byte >= width:
                    continue
                bank, half = divmod(byte, 2)
                value = expected[bank]
                byte_value = (data >> (8 * byte)) & 0xFF
                if half == 0:
                    value = (value & 0xFF00) | byte_value
                else:
                    value = (value & 0x00FF) | (byte_value << 8)
                expected[bank] = value
            assert write["data_values"][:4] == expected
            assert write["data_values"][4:] == banks[4:]

    # A mismatched compare value leaves the line untouched for every width.
    for cmd, mask in masks.items():
        if cmd == 0x18:
            word_idx = 4
            width = 16
        else:
            word_idx = 0
            width = {0x1A: 4, 0x1B: 8, 0x1C: 2, 0x1D: 1}[cmd]
        cmp_all_ones = (1 << (8 * width)) - 1
        mismatch = mp.atomic_op(vaddr=0x9200, paddr=0xF200, cmd=cmd,
                                amo_data=0xFFFFFFFFFFFFFFFF,
                                amo_mask=mask, amo_cmp=cmp_all_ones,
                                word_idx=word_idx, coh=DIRTY, banks=banks)
        assert mismatch["cas_match"] is False, hex(cmd)
        assert not any(snap["data_write"] for snap in mismatch["snapshots"])
        resp = first(mismatch["snapshots"], "atomic_resp")
        assert resp is not None
        # atomic_resp always returns the 16B window selected by word_idx
        # (two consecutive 8B words), independent of the CAS width.
        resp_base = word_idx * 4
        assert resp["atomic_data"] == line_from_banks(banks, resp_base, 8)

    # CAS on a line that is not cached goes to the miss queue instead.
    miss = mp.atomic_op(vaddr=0x9300, paddr=0xF300, cmd=M_XA_CASD,
                        amo_data=0xFFFFFFFF, amo_mask=0xFF, amo_cmp=0,
                        word_idx=0, coh=NOTHING, tag_match=False)
    assert miss["outcome"] == "miss"
    mreq = first(miss["snapshots"], "miss_req")
    assert mreq is not None and mreq["miss_cmd"] == M_XA_CASD
    assert mreq["miss_amo_mask"] == 0xFF


# MP-FP-015
def test_branch_to_trunk_grow_and_block(mp):
    # A Branch line needs a BtoT grow; the miss carries isBtoT and the replacer
    # is steered to the lowest non-BtoT way for the refill.
    for btot in (0b0000, 0b0001, 0b0010, 0b0011, 0b0101, 0b1100):
        want_next = 1 << next(way for way in range(4)
                              if not (btot >> way) & 1)
        result = mp.store_op(vaddr=0x9500, paddr=0xF500, data=0x55AA, mask=0xFF,
                             store_id=3, coh=BRANCH, hit_way=0, btot=btot)
        snaps = result["snapshots"]
        miss = first(snaps, "miss_req")
        assert miss is not None, bin(btot)
        assert miss["miss_isBtoT"] == 1
        assert miss["miss_cancel"] == 0
        assert result["s0"]["btot_ways"] == btot
        assert result["outcome"] == "miss_accepted"
        assert any(snap["s2_next_evict_way"] == want_next for snap in snaps),             (bin(btot), want_next)

    # Three BtoT ways in the set: the grow is refused and the store replays.
    for btot in (0b1110, 0b0111, 0b1111):
        blocked = mp.store_op(vaddr=0x9500, paddr=0xF500, data=0x55AA,
                              mask=0xFF, store_id=4, coh=BRANCH, hit_way=0,
                              btot=btot)
        bsnaps = blocked["snapshots"]
        assert blocked["outcome"] == "replay", bin(btot)
        replay = first(bsnaps, "store_replay")
        assert replay is not None
        bmiss = first(bsnaps, "miss_req")
        assert bmiss is not None and bmiss["miss_cancel"] == 1
        assert first(bsnaps, "store_hit") is None


# MP-FP-015
def test_btot_evict_retry_uses_occupy_way(mp):
    # MissQueue re-issues a refill after a BtoT eviction conflict; MainPipe must
    # install into the way MissQueue picked (occupy_way), not the replacer way.
    result = mp.refill_op(vaddr=0x6400, paddr=0xF400, cmd=M_XRD,
                          replace_way=0, occupy_way=0b0100,
                          evict_btot=True)
    snaps = result["snapshots"]
    tag = first(snaps, "tag_write")
    assert tag is not None
    assert tag["tag_write_way"] == 0b0100
    meta = first(snaps, "meta_write")
    assert meta is not None and meta["meta_write_way"] == 0b0100
    data = first(snaps, "data_write")
    assert data is not None and data["data_wmask"] == 0xFFFFFFFF


# MP-FP-007
def test_probe_tot_on_branch_and_nothing(mp):
    # toT on a Branch line is a pure report (BtoB) and leaves coh unchanged.
    branch = mp.probe_op(vaddr=0x5400, paddr=0xE400, param=0, need_data=False,
                         coh=BRANCH, hit_way=1, banks=default_banks(0xA00))
    wb = first(branch["snapshots"], "wb")
    assert wb is not None and wb["wb_param"] == BTOB
    assert wb["wb_hasdata"] == 0
    assert first(branch["snapshots"], "meta_write") is None

    # toT probe that misses reports NtoN.
    missing = mp.probe_op(vaddr=0x5500, paddr=0xE500, param=0,
                          need_data=False, coh=DIRTY, tag_match=False,
                          replace_way=3)
    mwb = first(missing["snapshots"], "wb")
    assert mwb is not None and mwb["wb_param"] == NTON
    assert mwb["wb_hasdata"] == 0


# MP-FP-016
def test_probe_flag_error_reporting(mp):
    for kind in ("denied", "corrupt"):
        result = mp.probe_op(vaddr=0x9600, paddr=0xF600, param=1,
                             need_data=True, coh=DIRTY, hit_way=1,
                             extra_error=(1, kind))
        snaps = result["snapshots"]
        err = first(snaps, "error_valid")
        assert err is not None, kind
        assert err["error_report"] == 0, kind
        assert err["error_paddr"] == block_addr(0xF600), kind
        wb = first(snaps, "wb")
        assert wb is not None and wb["wb_hasdata"] == 1


# MP-FP-017
def test_ecc_error_reporting(mp):
    # A corrupted tag ECC codeword is detected as an error and the request is
    # treated as a probe miss (NtoN) with corrupt writeback data.
    tagged = mp.probe_op(vaddr=0x9700, paddr=0xF700, param=1, need_data=True,
                         coh=DIRTY, hit_way=1, tag_ecc_bad=True)
    tsnaps = tagged["snapshots"]
    terr = first(tsnaps, "error_valid")
    assert terr is not None
    assert terr["error_report"] == 1
    assert terr["error_paddr"] == block_addr(0xF700)
    twb = first(tsnaps, "wb")
    assert twb is not None and twb["wb_param"] == NTON
    assert twb["wb_hasdata"] == 0 and twb["wb_corrupt"] == 1

    # Bank data ECC error on the probe read: the line is still released but is
    # marked corrupt and reported to the BEU.
    data = mp.probe_op(vaddr=0x9800, paddr=0xF800, param=1, need_data=True,
                       coh=DIRTY, hit_way=0, readline_error=True)
    dsnaps = data["snapshots"]
    derr = first(dsnaps, "error_valid")
    assert derr is not None
    assert derr["error_report"] == 1
    dwb = first(dsnaps, "wb")
    assert dwb is not None and dwb["wb_hasdata"] == 1
    assert dwb["wb_corrupt"] == 1


# MP-FP-001 / MP-FP-012
def test_back_to_back_same_set_stores(mp):
    # The first store occupies S0; the second one targets the same set and must
    # wait in the skid buffer (store_req_ready drops) before being accepted.
    first_op = mp.store_op(vaddr=0x1100, paddr=0xA100, data=0x1111, mask=0xFF,
                           store_id=1, coh=DIRTY, hit_way=0, hold=1, cycles=1)
    second_op = mp.store_op(vaddr=0x1100, paddr=0xA100, data=0x2222, mask=0xFF,
                            store_id=2, coh=DIRTY, hit_way=0, hold=10, cycles=10)
    snaps = [*first_op["snapshots"], *second_op["snapshots"]]
    assert any(snap["store_ready"] == 0 for snap in snaps)
    hits = [snap["store_hit_id"] for snap in snaps if snap["store_hit"]]
    assert 1 in hits and 2 in hits
    read_idx = [snap["tag_read_idx"] for snap in snaps if snap["tag_read"]]
    assert all(idx == dcache_index(0x1100) for idx in read_idx)


# MP-FP-016
def test_flag_error_uses_registered_bits_when_s1_stalls(mp):
    # Stalling S1 (data_readline not ready) makes the next S2 capture take the
    # registered extra-meta corrupt bit rather than the live response.
    result = mp.probe_op(vaddr=0x9900, paddr=0xF900, param=1, need_data=True,
                         coh=DIRTY, hit_way=0, extra_error=(0, "corrupt"),
                         stall_readline_at=1)
    snaps = result["snapshots"]
    err = first(snaps, "error_valid")
    assert err is not None
    assert err["error_report"] == 0
    assert err["error_paddr"] == block_addr(0xF900)
    wb = first(snaps, "wb")
    assert wb is not None
