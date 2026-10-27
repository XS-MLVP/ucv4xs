from dataclasses import replace

import pytest

from lsqverify.raw.types import SqPtr


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("control", ("young", "invalid", "disjoint", "same_va", "other_page"))
async def test_cross_word_alias_necessary_condition_controls(forward, lane, control):
    env = forward
    older = env.store(vaddr=0x10010, size=2, data=0x11111111)
    younger = env.store(vaddr=0x2000C, size=3, data=0x2222222222222222)
    sq = 2
    if control == "young":
        sq = 1
    elif control == "invalid":
        younger = replace(younger, address_ready=False)
    elif control == "disjoint":
        younger = env.store(vaddr=0x20014, size=2, data=0x22222222)
    elif control == "same_va":
        younger = env.store(vaddr=0x1000C, size=3, data=0x2222222222222222)
    elif control == "other_page":
        younger = replace(younger, page=younger.page + 1)
    scenes = {"young": ("FWD-REG.negative_young", "FWD-AGE.young_excluded"),
              "invalid": ("FWD-REG.negative_invalid", "FWD-WAIT.address"),
              "disjoint": ("FWD-REG.negative_disjoint", "FWD-BYTE.no_overlap"),
              "same_va": ("FWD-CROSS.next_word", "FWD-SELECT.multi_partial"),
              "other_page": ("FWD-VAPA.agree",)}[control]
    await env.request(env.query(vaddr=0x10010, sq=sq, size=2), older.paddr, lane=lane,
                      stores=env.bank({0: older, 1: younger}), scenes=scenes)


@pytest.mark.parametrize("lane", range(3))
async def test_low_age_segment_priority_subtree_at_high_physical_slot(forward, lane):
    env = forward
    store = env.store()
    await env.cycle(dequeue=SqPtr.encode(60), upper=SqPtr.encode(124))
    await env.request(env.query(sq=114), store.paddr, lane=lane, stores=env.bank({48: store}),
                      scenes=("FWD-AGE.wrap", "FWD-AGE.flags"))


@pytest.mark.parametrize("lane", range(3))
async def test_all_physical_store_slots_produce_checked_forward_bytes(forward, lane):
    env = forward
    for slot in range(64):
        store = env.store(data=0x0102030405060708 ^ (slot << 8))
        await env.cycle(dequeue=SqPtr.encode(slot), upper=SqPtr.encode(slot + 64))
        await env.request(env.query(sq=slot + 1), store.paddr, lane=lane, stores=env.bank({slot: store}),
                          scenes=("FWD-AGE.all_slots", "FWD-AGE.flags"))
