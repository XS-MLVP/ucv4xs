
from dataclasses import replace
import hashlib

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.store_payload import add_digest
from suites.memblock.lsq.vlq.types import QueuePtr, RobPtr
from suites.memblock.lsq.vsq_recovery import PublicWindow, WINDOWS, save
from .memory_owners import StoreOwner, cached_load
from .recovery_owners import RecoveryOwners


class PublicRecoveryOwners(RecoveryOwners):
    def __init__(self, env):
        super().__init__(env)
        self.window = None

    async def cycle(self, **fields):
        await super().cycle(**fields)
        if self.window is not None:
            self.window.observe(self.env.observed, self.env.last_tick)


def store(position, rob, generation):
    return StoreOwner(position, RobPtr.encode(rob), 0x200000 + (generation * 1024 + position) * 64,
                      0xA000000 + (generation * 1024 + position) * 64,
                      value=0x1020304000000000 | generation << 16 | position)


def check_word(pins, lane, owner):
    prefix = P.io(f"forward_{lane}_s2Resp_")
    want = {prefix + "valid": 1, **{prefix + "bits_" + flag: 0 for flag in
            ("forwardInvalid", "matchInvalid", "addrInvalid_valid", "dataInvalid_valid")}}
    for byte in range(16):
        want[prefix + f"bits_forwardMask_{byte}"] = int(byte < 8)
        if byte < 8:
            want[prefix + f"bits_forwardData_{byte}"] = owner.value >> (8 * byte) & 255
    assert all(pins[key] == value for key, value in want.items()), ("release-survivor-original-bytes", {key: [pins[key], value] for key, value in want.items() if pins[key] != value})


@pytest.mark.parametrize("delay", range(3))
async def test_shared_retired_prefix_phases_real_Loads_Store_bytes_and_reused_UIDs(lsq, tmp_path, delay):
    trace, profiles, stream, program = PublicRecoveryOwners(lsq), [], hashlib.sha256(), 10
    for profile, (base, prefix) in enumerate(WINDOWS):
        trace.base = replace(trace.base, pending=RobPtr.encode(program - 1), pending_next=RobPtr.encode(program - 1), sbuffer_ready=(False, False))
        fillers = [store(pos, program + offset, profile) for offset, pos in enumerate(range(trace.sq_head, base))]
        if fillers:
            await trace.dispatch(stores=fillers)
            program += len(fillers)
            await trace.write_all(owner.position for owner in fillers)
            await trace.finish(pending=RobPtr.encode(program))
        assert trace.sq_head == base
        trace.base = replace(trace.base, pending=RobPtr.encode(program - 1), pending_next=RobPtr.encode(program - 1), sbuffer_ready=(False, False))
        owners = [store(base + index, program + index + int(index > prefix), profile + 4) for index in range(prefix + 5)]
        first, cutoff, cut = owners[prefix], owners[prefix + 1], base + prefix + 2
        kept_load = cached_load(2 * profile, program + prefix + 1, base + prefix + 1, first.vaddr, first.paddr)
        killed_load = cached_load(2 * profile + 1, program + prefix + 6, base + prefix + 5, owners[-1].vaddr, owners[-1].paddr)
        await trace.dispatch(owners, [kept_load, killed_load])
        await trace.write_all(owner.position for owner in owners)
        pins = await trace.forward(kept_load, delay)
        check_word(pins, delay, first)
        await trace.execute([kept_load]); await trace.idle(8)
        assert trace.active_loads[kept_load.execution.uop.lq]["completed"]
        assert trace.sq_head == base and all(not trace.stores[owner.position]["consumed"] for owner in owners)
        trace.base = replace(trace.base, pending=first.rob, pending_next=first.rob)
        await trace.idle(delay + 1)
        # First redirect still sees the original ROB head. Subsequent cycles
        # monotonically move to the completed Load's following cutoff Store.
        trace.base = replace(trace.base, pending=cutoff.rob, pending_next=cutoff.rob)
        trace.window = PublicWindow("lsq_wrapper")
        assert await trace.cancel(cutoff.rob, flush_self=False, pending=first.rob, pending_next=first.rob) == (QueuePtr.encode(2 * profile + 1), cut % 256)
        recovery = trace.window.finish(cut, 2 * profile + 1)
        trace.window = None
        victims = [state for state in trace.abort_history if "owner" in state and state["owner"] in owners]
        assert len(victims) == 3 and all(not state["consumed"] for state in victims)
        cutoff_program = program + prefix + 2
        replacements = [store(cut + index, cutoff_program + index + 1, profile + 12) for index in range(3)]
        new_load = cached_load(2 * profile + 1, cutoff_program + 4, base + prefix + 5, replacements[-1].vaddr, replacements[-1].paddr)
        await trace.dispatch(replacements, [new_load])
        await trace.write_all(owner.position for owner in replacements)
        pins = await trace.forward(new_load, delay)
        check_word(pins, delay, replacements[-1])
        await trace.execute([new_load])
        program = cutoff_program + 5
        await trace.finish(pending=RobPtr.encode(program))
        assert trace.sq_head == base + prefix + 5
        assert all(trace.stores[owner.position]["completed"] for owner in owners[:prefix + 2] + replacements)
        assert trace.active_loads[new_load.execution.uop.lq]["completed"]
        item = dict(profile=profile, base=base, retired_prefix=prefix, old_store_uids=len(owners),
                    fillers_completed=len(fillers), actual_sq_cut=cut % 256,
                    cancelled_store_uids=[state["uid"] for state in victims],
                    replacement_store_uids=[trace.stores[owner.position]["uid"] for owner in replacements],
                    retained_store_completions=prefix + 2, new_store_completions=3,
                    original_Load_completed=trace.active_loads[kept_load.execution.uop.lq]["uid"],
                    reused_Load_completed=trace.active_loads[new_load.execution.uop.lq]["uid"],
                    query_lane=delay, recovery=recovery)
        profiles.append(item); add_digest(stream, item)
        for owner in owners[:prefix + 2] + replacements:
            state = trace.stores[owner.position]
            add_digest(stream, ["original_bytes_fire_then_dequeue", state["uid"], owner.position, state["last_fire"]])
    assert len(trace.stores) == len(trace.fragments_fired) == trace.sq_head == 254
    assert len(trace.loads) == 12 and trace.load_released == 8 and len(trace.cancelled) == 4
    assert len([state for state in trace.abort_history if "owner" in state]) == 12
    lsq.prove("LSQ-RECOVER.partial", "LSQ-RECOVER.retired_store", "LSQ-RECOVER.reuse", "LSQ-FORWARD.sqid")
    save(tmp_path / "vsq-release-walk-witness.json", "lsq_wrapper", delay, profiles, stream,
         normal_store_completions=254, cancelled_store_uids=12, original_Load_completions=4,
         reused_Load_completions=4, cancelled_Load_uids=4, actual_Sbuffer_fragments=254,
         scope="real two-branch dispatch/redirect/tails, original Load bytes+S3 before ROB advancement, cancelled Load slot reused with new original S3, retained/new Store bytes and normal dequeue")
