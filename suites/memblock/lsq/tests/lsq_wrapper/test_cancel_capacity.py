
from dataclasses import replace
import hashlib

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.store_payload import add_digest
from suites.memblock.lsq.vlq.types import QueuePtr, RobPtr
from suites.memblock.lsq.vsq_cancel_capacity import save
from suites.memblock.lsq.vsq_recovery import PublicWindow
from .memory_owners import StoreOwner, cached_load
from .recovery_owners import RecoveryOwners


class ObservedRecovery(RecoveryOwners):
    def __init__(self, env):
        super().__init__(env)
        self.observation = None

    async def cycle(self, **fields):
        await super().cycle(**fields)
        if self.observation is not None:
            self.observation.observe(self.env.observed, self.env.last_tick)


def owner(position, program, generation):
    return StoreOwner(position, RobPtr.encode(program), 0x600000 + generation * 65536 + position * 64,
                      0xC000000 + generation * 65536 + position * 64,
                      value=0x1020304000000000 | generation << 16 | position)


def check(pins, lane, store):
    prefix = P.io(f"forward_{lane}_s2Resp_")
    expected = {prefix + "valid": 1, **{prefix + "bits_" + flag: 0 for flag in
                ("forwardInvalid", "matchInvalid", "addrInvalid_valid", "dataInvalid_valid")}}
    for byte in range(16):
        expected[prefix + f"bits_forwardMask_{byte}"] = int(byte < 8)
        if byte < 8:
            expected[prefix + f"bits_forwardData_{byte}"] = store.value >> (8 * byte) & 255
    assert all(pins[key] == value for key, value in expected.items()), ("cancel-capacity-original-bytes", {key: [pins[key], value] for key, value in expected.items() if pins[key] != value})


async def test_shared_deep_suffix_all_cancel_every_Store_slot_and_original_Loads(lsq, tmp_path):
    trace, profiles, stream, program, lq = ObservedRecovery(lsq), [], hashlib.sha256(), 10, 0
    for profile, (base, count, kept) in enumerate(((0, 16, 2), (62, 64, 0))):
        trace.base = replace(trace.base, pending=RobPtr.encode(program - 1), pending_next=RobPtr.encode(program - 1), sbuffer_ready=(False, False))
        fillers = [owner(pos, program + index, profile) for index, pos in enumerate(range(trace.sq_head, base))]
        if fillers:
            await trace.dispatch(stores=fillers)
            program += len(fillers)
            await trace.write_all(item.position for item in fillers)
            await trace.finish(pending=RobPtr.encode(program))
        assert trace.sq_head == base
        trace.base = replace(trace.base, pending=RobPtr.encode(program - 1), pending_next=RobPtr.encode(program - 1), sbuffer_ready=(False, False))
        old = [owner(base + index, program + index + int(bool(kept) and index > 0), profile + 4) for index in range(count + kept)]
        keep_load = cached_load(lq, program + 1, base + 1, old[0].vaddr, old[0].paddr) if kept else None
        killed_lq = lq + int(bool(kept))
        killed_load = cached_load(killed_lq, program + len(old) + int(bool(kept)), base + len(old), old[-1].vaddr, old[-1].paddr)
        await trace.dispatch(stores=old, loads=([keep_load] if kept else []) + [killed_load])
        await trace.write_all(item.position for item in old)
        if keep_load:
            check(await trace.forward(keep_load, profile), profile, old[0])
            await trace.execute([keep_load]); await trace.idle(8)
            assert trace.active_loads[keep_load.execution.uop.lq]["completed"]
        assert trace.sq_head == base and all(not trace.stores[item.position]["consumed"] for item in old)
        cutoff = old[kept - 1] if kept else old[0]
        cut = base + kept
        old_states = [trace.stores[item.position] for item in old[kept:]]
        trace.observation = PublicWindow("lsq_wrapper")
        assert await trace.cancel(cutoff.rob, flush_self=not kept) == (QueuePtr.encode(killed_lq), cut % 256)
        recovery = trace.observation.finish(cut, killed_lq)
        trace.observation = None
        replacement_program = program + kept + int(bool(kept))
        new = [owner(cut + index, replacement_program + index, profile + 12) for index in range(count)]
        new_load = cached_load(killed_lq, replacement_program + count, base + len(old), new[-1].vaddr, new[-1].paddr)
        await trace.dispatch(stores=new, loads=[new_load])
        await trace.write_all(item.position for item in new)
        check(await trace.forward(new_load, profile), profile, new[-1])
        await trace.execute([new_load])
        program = replacement_program + count + 1
        await trace.finish(pending=RobPtr.encode(program))
        reuse = [[state["uid"], trace.stores[item.position]["uid"], item.position] for state, item in zip(old_states, new)]
        assert all(not state["consumed"] and state["uid"] < trace.stores[item.position]["uid"]
                   and trace.stores[item.position]["completed"] for state, item in zip(old_states, new))
        assert all(trace.stores[item.position]["completed"] for item in old[:kept])
        item = dict(profile=profile, physical_base=base, cancel_uops=count, kept_uops=kept, physical_flows=len(old),
                    fillers_completed=len(fillers), actual_recovered_tail=cut % 256, reuse_old_new_position=reuse,
                    new_completed_uids=[trace.stores[item.position]["uid"] for item in new], recovery=recovery,
                    original_Load_completions=int(bool(kept)), new_Load_completions=1, cancelled_Load_uids=1)
        profiles.append(item); add_digest(stream, item)
        lq = killed_lq + 1
    assert trace.sq_head == len(trace.stores) == len(trace.fragments_fired) == 126
    assert trace.load_released == 3 and len(trace.cancelled) == 2
    assert len([state for state in trace.abort_history if "owner" in state]) == 80
    lsq.prove("LSQ-RECOVER.partial", "LSQ-RECOVER.all", "LSQ-RECOVER.reuse", "LSQ-FORWARD.sqid")
    save(tmp_path / "vsq-cancel-capacity-witness.json", "lsq_wrapper", profiles, stream,
         normal_store_uids=126, cancelled_store_uids=80, exact_physical_slot_reuses=80,
         actual_Sbuffer_fragments=126, normal_Load_uids=3, cancelled_Load_uids=2)
