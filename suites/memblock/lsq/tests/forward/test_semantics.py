"""Remaining semantic cases; line coverage is already full, not a sign-off."""
from dataclasses import replace
import random

import pytest

from lsqverify.raw.types import SqPtr
from lsqverify.forward.types import SecondPage, Translation, byte_count


@pytest.mark.parametrize("lane", range(3))
async def test_all_sizes_offsets_and_mask_holes(forward, lane):
    env = forward
    data = 0x0F0E0D0C0B0A09080706050403020100
    for size in range(8):
        for offset in range(16):
            source = env.store(size=size, vaddr=0x10000 + offset, data=data)
            query = env.query(size=size, vaddr=source.vaddr)
            await env.request(query, source.paddr, lane=lane, stores=env.bank({0: source}),
                              scenes=("FWD-BYTE.sizes", "FWD-BYTE.offsets", "FWD-CROSS.same_word",
                                      *( ("FWD-BYTE.q_encodings",) if size >= 4 else () )))
    for mask in (0, 0xFFFF, 0xAAAA, 0x5555, *(1 << i for i in range(16)), *(0xFFFF ^ (1 << i) for i in range(16))):
        source = env.store(size=4, vaddr=0x10000, mask=mask, data=data)
        await env.request(env.query(size=4), source.paddr, lane=lane, stores=env.bank({0: source}), scenes=("FWD-BYTE.mask",))


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("store_start,load_start", ((4, 0), (0, 4), (4, 6), (12, 16), (15, 16)))
async def test_partial_and_next_word_byte_ranges(forward, lane, store_start, load_start):
    env = forward
    source = env.store(size=3, vaddr=0x10000 + store_start, data=0x8877665544332211)
    query = env.query(size=2, vaddr=0x10000 + load_start)
    await env.request(query, source.page * 4096 + query.vaddr % 4096, lane=lane, stores=env.bank({0: source}),
                      scenes=("FWD-BYTE.partial", "FWD-CROSS.next_word" if load_start >= 16 else "FWD-CROSS.same_word"))


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("ready", (False, True))
async def test_youngest_match_cannot_fall_back_when_its_data_is_missing(forward, lane, ready):
    env = forward
    older = env.store(size=4, data=0x11111111111111111111111111111111)
    newer = env.store(size=4, data=0x22222222222222222222222222222222, ready=ready)
    await env.request(env.query(sq=2, size=4), older.paddr, lane=lane, stores=env.bank({0: older, 1: newer}),
                      scenes=("FWD-SELECT.youngest", "FWD-SELECT.full", *( ("FWD-SELECT.no_fallback",) if not ready else () )))


@pytest.mark.parametrize("lane", range(3))
async def test_retired_slots_are_not_current_producers(forward, lane):
    env = forward
    live = env.store(data=0x5555555555555555)
    retired = env.store(data=0x9999999999999999)
    await env.cycle(dequeue=SqPtr.encode(10), upper=SqPtr.encode(74))
    await env.request(env.query(sq=11), live.paddr, lane=lane, stores=env.bank({9: retired, 10: live}), scenes=("FWD-AGE.retired_excluded",))


@pytest.mark.parametrize("lane", range(3))
async def test_load_beyond_physical_window_still_checks_last_real_store(forward, lane):
    env = forward
    source = env.store(data=0x6363636363636363)
    await env.request(env.query(sq=65), source.paddr, lane=lane, stores=env.bank({63: source}), scenes=("FWD-AGE.window_limit",))


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("load_sq", (124, 127, 128, 129))
async def test_missing_data_dependency_keeps_original_sq_flags_beyond_window(forward, lane, load_sq):
    env = forward
    source = env.store(ready=False)
    await env.cycle(dequeue=SqPtr.encode(60), upper=SqPtr.encode(124))
    await env.request(env.query(sq=load_sq), source.paddr, lane=lane, stores=env.bank({48: source}),
                      scenes=("FWD-WAIT.identity", "FWD-AGE.window_limit", "FWD-AGE.flags",
                              *(("FWD-WAIT.clipped_identity",) if load_sq >= 128 else ())))


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("mode", ("strict_missing", "strict_ready", "strict_outside", "precise_missing", "precise_ready", "retired", "outside"))
async def test_strict_and_precise_address_dependencies(forward, lane, mode):
    env = forward
    source = env.store()
    target = replace(env.store(vaddr=0x20000, page=0xDEF), address_ready=mode not in ("strict_missing", "precise_missing"))
    bank = env.bank({0: source, 1: target})
    query = env.query(sq=2, strict=mode.startswith("strict"), wait=not mode.startswith("strict"), wait_sq=SqPtr.encode(1))
    scenes = ["FWD-WAIT.strict" if query.strict else "FWD-WAIT.precise"]
    if mode == "strict_outside":
        bank = env.bank({slot: source if slot == 0 else env.store(vaddr=0x30000 + slot * 64, page=0xDEF) for slot in range(64)})
        query = env.query(sq=65, strict=True)
        scenes.append("FWD-AGE.window_limit")
    elif mode == "retired":
        await env.cycle(dequeue=SqPtr.encode(1), upper=SqPtr.encode(65))
        query = env.query(sq=2, wait=True, wait_sq=SqPtr.encode(0))
        bank = env.bank({1: source})
        scenes.append("FWD-WAIT.retired")
    elif mode == "outside":
        query = env.query(sq=2, wait=True, wait_sq=SqPtr.encode(64))
        scenes.append("FWD-WAIT.outside")
    await env.request(query, source.paddr, lane=lane, stores=bank, scenes=scenes)


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("kind", range(4))
async def test_cbo_zero_and_other_suboperations_in_same_cacheline(forward, lane, kind):
    env = forward
    source = replace(env.store(size=4, data=0), cache_operation=True, cbo=kind)
    for word in range(4):
        query = env.query(vaddr=source.vaddr + word * 16, size=4)
        await env.request(query, source.paddr + word * 16, lane=lane, stores=env.bank({0: source}),
                          scenes=("FWD-CBO.line", "FWD-CBO.zero" if kind == 3 else "FWD-CBO.other"))


@pytest.mark.parametrize("page_lane", (0, 1))
@pytest.mark.parametrize("load_lane", range(3))
@pytest.mark.parametrize("relation", ("older", "equal", "younger", "disabled", "wrong_page"))
async def test_second_page_valid_full_sq_age_and_match_domain(forward, page_lane, load_lane, relation):
    env = forward
    # An actual cross-page older store: only UQ supplies its noncontiguous
    # second PA. VA page-tag matching must not fabricate a next-word forward.
    source = env.store(vaddr=0x10FFC, size=3)
    query = env.query(vaddr=0x11000, sq=2, size=2)
    sq = {"older": 0, "equal": 2, "younger": 3, "disabled": 0, "wrong_page": 0}[relation]
    page = SecondPage(relation != "disabled", 0xDEF000 + (4096 if relation == "wrong_page" else 0), SqPtr.encode(sq))
    pages = tuple(page if i == page_lane else SecondPage() for i in range(2))
    scenes = (f"FWD-UQ.lane{page_lane}", "FWD-CROSS.page_boundary") if relation == "older" else (
        "FWD-UQ.disabled" if relation in ("disabled", "wrong_page") else "FWD-UQ.young",)
    await env.cycle(second_pages=pages)
    await env.request(query, 0xDEF000, lane=load_lane, stores=env.bank({0: source}), scenes=scenes)


@pytest.mark.parametrize("base", (63, 127, 191, 255))
async def test_second_page_comparison_respects_every_sq_flag_boundary(forward, base):
    env = forward
    query = env.query(sq=base + 1, vaddr=0x11000, size=2)
    page = SecondPage(True, 0xDEF000, SqPtr.encode(base))
    await env.cycle(dequeue=SqPtr.encode(base), upper=SqPtr.encode(base + 64), second_pages=(SecondPage(), page))
    await env.request(query, page.paddr, lane=base % 3, scenes=("FWD-UQ.flags",))


@pytest.mark.parametrize("lane", range(3))
async def test_same_va_different_pa_and_physical_only_matches_replay(forward, lane):
    env = forward
    source = env.store()
    await env.request(env.query(), source.paddr + 4096, lane=lane, stores=env.bank({0: source}), scenes=("FWD-VAPA.disagree",))
    alias = replace(source, vaddr=0x20000)
    await env.request(env.query(), source.paddr, lane=lane, stores=env.bank({0: alias}), scenes=("FWD-VAPA.physical_only",))


@pytest.mark.parametrize("lane", range(3))
async def test_s1_kill_has_no_response_and_next_uid_reuses_lane_safely(forward, lane):
    env = forward
    source = env.store(size=4, data=0xFFEEDDCCBBAA99887766554433221100)
    first = env.query(size=0)
    change = await env.cycle({lane: first}, stores=env.bank({0: source}))
    old_uid = change["accepted"][0]["uid"]
    new_query = env.query(vaddr=0x10003, size=1)
    change = await env.cycle({lane: new_query}, {lane: Translation(source.paddr, True)})
    assert [job["uid"] for job in change["killed"]] == [old_uid]
    assert not env.observed[f"io_query_{lane}_s2Resp_valid"]
    new_uid = change["accepted"][0]["uid"]
    env.coverage.arm_kill_reuse(("FWD-PIPE.kill", "FWD-PIPE.kill_reuse"), [old_uid], [new_uid], env.last_tick)
    change = await env.cycle(translations={lane: Translation(source.paddr + 3)})
    assert [answer["uid"] for answer in change["responses"]] == [new_uid]
    await env.idle(2)


async def test_back_to_back_three_lanes_and_query_holes_do_not_mix_generations(forward):
    env = forward
    source = env.store(size=4, data=0x0F0E0D0C0B0A09080706050403020100)
    await env.cycle(stores=env.bank({0: source}))
    previous = {}
    for tick in range(70):
        current = {lane: env.query(vaddr=0x10000 + (tick * 3 + lane) % 16, size=(tick + lane) % 8) for lane in range(3) if (tick + lane) % 5}
        translations = {lane: Translation(source.page * 4096 + query.vaddr % 4096) for lane, query in previous.items()}
        change = await env.cycle(current, translations)
        if change["responses"]:
            env.arm(("FWD-PIPE.back_to_back", "FWD-PIPE.holes"), [answer["uid"] for answer in change["responses"]])
        previous = current
    await env.cycle(translations={lane: Translation(source.page * 4096 + query.vaddr % 4096) for lane, query in previous.items()})
    await env.idle(2)
    assert env.model.sequence == len(env.coverage.completed)


@pytest.mark.parametrize("lane", range(3))
async def test_s2_mdp_uses_current_address_ready_not_old_snapshot(forward, lane):
    env = forward
    source = env.store()
    target = replace(env.store(vaddr=0x20000, page=0xDEF), address_ready=False)
    change = await env.cycle({lane: env.query(sq=2, wait=True, wait_sq=SqPtr.encode(1))}, stores=env.bank({0: source, 1: target}))
    uid = change["accepted"][0]["uid"]
    await env.cycle(translations={lane: Translation(source.paddr)})
    assert env.observed[f"io_query_{lane}_s2Resp_bits_addrInvalid_valid"]
    env.arm("FWD-LIVE.mdp", [uid])
    await env.cycle(stores=env.bank({0: source, 1: replace(target, address_ready=True)}))
    assert not env.pre_observed[f"io_query_{lane}_s2Resp_bits_addrInvalid_valid"]
    await env.idle(2)


@pytest.mark.parametrize("lane", range(3))
async def test_retirement_reuse_keeps_s1_data_but_s2_physical_cam_is_live(forward, lane):
    env = forward
    old = env.store(data=0xAAAAAAAAAAAAAAAA)
    new = env.store(vaddr=0x20000, page=0xDEF, data=0xBBBBBBBBBBBBBBBB)
    await env.cycle(dequeue=SqPtr.encode(63), upper=SqPtr.encode(127))
    change = await env.cycle({lane: env.query(sq=64)}, stores=env.bank({63: old}))
    uid = change["accepted"][0]["uid"]
    await env.cycle(translations={lane: Translation(old.paddr)})
    env.arm(("FWD-LIVE.data_snapshot", "FWD-LIVE.physical_cam", "FWD-LIVE.boundaries"), [uid])
    await env.cycle(dequeue=SqPtr.encode(64), upper=SqPtr.encode(128), stores=env.bank({63: new}))
    prefix = f"io_query_{lane}_s2Resp_"
    assert env.pre_observed[prefix + "valid"] and env.pre_observed[prefix + "bits_matchInvalid"]
    assert sum(env.pre_observed[prefix + f"bits_forwardData_{i}"] << (8 * i) for i in range(8)) == old.data
    await env.request(env.query(sq=128, vaddr=new.vaddr), new.paddr, lane=lane, stores=env.bank({63: new}), scenes=("FWD-REUSE.identity",))


async def test_disabled_bank_and_query_payload_do_not_create_work(forward):
    env = forward
    source = env.store()
    dirty = replace(env.store(vaddr=0x20000, page=0xDEF, data=(1 << 128) - 1), address_ready=False)
    await env.cycle(queries={0: replace(env.query(), valid=False)}, stores=env.bank({0: dirty, 7: dirty}),
                    second_pages=(SecondPage(False, 0xABC000, SqPtr.encode(0)), SecondPage(False, 0xABC000, SqPtr.encode(255))))
    await env.idle(4)
    assert not any(env.observed[f"io_query_{lane}_s2Resp_valid"] for lane in range(3))
    await env.request(env.query(), source.paddr, stores=env.bank({0: source, 7: dirty}), scenes=("FWD-IDLE.disabled",))


async def _seeded_stream(env, seed, *, producer_masks, aligned):
    rng = random.Random(seed)
    env.coverage.sample(("FWD-CONCURRENT.seeded",), env.last_tick)
    for epoch in range(5):
        base = (63 * epoch + (seed % 64)) % 256
        bank, queries_by_position = {}, []
        for position in range(64):
            address = 0x10000 + position * 64 + rng.randrange(16)
            size = rng.randrange(8)
            if aligned:
                address = address // 16 * 16
            data = rng.getrandbits(128)
            sampled_mask = rng.getrandbits(byte_count(size))
            store = env.store(vaddr=address, page=0xABC, size=size, data=data,
                              mask=(1 << byte_count(size)) - 1 if producer_masks else sampled_mask, ready=rng.random() < 0.8)
            store = replace(store, address_ready=rng.random() < 0.85)
            bank[(base + position) % 64] = store
            queries_by_position.append(store)
        await env.cycle(dequeue=SqPtr.encode(base), upper=SqPtr.encode(base + 64), stores=env.bank(bank))
        previous = {}
        for tick in range(90):
            current = {}
            for lane in range(3):
                if rng.random() < 0.25:
                    continue
                age = rng.randrange(65)
                position = rng.randrange(64)
                target = queries_by_position[position]
                vaddr = target.vaddr // 16 * 16 + rng.choice((0, 16)) + rng.randrange(16)
                current[lane] = env.query(vaddr=vaddr, sq=base + age, size=rng.randrange(8), wait=rng.random() < 0.4,
                                          strict=rng.random() < 0.3, wait_sq=SqPtr.encode(base + rng.randrange(-8, 80)))
            translations = {lane: Translation(0xABC000 + query.vaddr % 4096, rng.random() < 0.12) for lane, query in previous.items()}
            change = await env.cycle(current, translations)
            previous = current
        await env.cycle(translations={lane: Translation(0xABC000 + query.vaddr % 4096) for lane, query in previous.items()})
        await env.idle(2)
    assert env.model.sequence == len(env.coverage.completed) + len(env.coverage.killed)
    assert not any(env.model.stage1) and not any(env.model.stage2)
    env.arm("FWD-CONCURRENT.seeded", sorted(env.coverage.completed))
    await env.idle(1)


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_in_window_nonalias_concurrent_byte_queries(forward, seed):
    """UNIT-INTERFACE mask-hole stress, retained separately from real PSQ masks."""
    await _seeded_stream(forward, seed, producer_masks=False, aligned=False)


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_real_psq_masks_with_cross_word_byte_queries(forward, seed):
    await _seeded_stream(forward, seed, producer_masks=True, aligned=False)


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_aligned_store_pipeline_and_fair_drain(forward, seed):
    # An additional partition, not a replacement for either cross-word or
    # mask-hole stress: all three remain ordinary tests and failures persist.
    await _seeded_stream(forward, seed, producer_masks=True, aligned=True)


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("word", (0, 1))
async def test_cross_word_store_mask_cannot_wrap_bytes_into_unwritten_addresses(forward, lane, word):
    env = forward
    # This is the real PSQ scalar producer mask, not an arbitrary hole mask:
    # an 8B store at +12 writes only 12..19, and the 16B load is word-aligned.
    source = env.store(vaddr=0x1000C, size=3, data=0x8877665544332211, mask=0xFF)
    query = env.query(vaddr=0x10000 + word * 16, size=4)
    await env.request(query, source.page * 4096 + query.vaddr % 4096, lane=lane,
                      stores=env.bank({0: source}), scenes=("FWD-BYTE.range_mask",))


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("store_offset,store_size,load_offset,load_size", (
    (12, 2, 0, 4), (8, 3, 0, 4), (12, 3, 12, 2), (12, 3, 16, 2), (12, 3, 0, 2),
))
async def test_range_mask_necessary_condition_controls(forward, lane, store_offset, store_size, load_offset, load_size):
    env = forward
    source = env.store(vaddr=0x10000 + store_offset, size=store_size, data=0x8877665544332211)
    query = env.query(vaddr=0x10000 + load_offset, size=load_size)
    await env.request(query, source.page * 4096 + query.vaddr % 4096, lane=lane,
                      stores=env.bank({0: source}), scenes=("FWD-BYTE.partial",))
