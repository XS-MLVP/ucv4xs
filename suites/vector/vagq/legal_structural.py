"""Protocol-constrained structural stimulus with independent semantic checks.

The historical unconstrained stateful scans could acknowledge nonexistent
operations and issue simultaneous requests to the same entry. Native source
assertions remain enabled; these sweeps use complete admitted lifecycles.
SPDX-License-Identifier: MPL-2.0
"""
import random


async def sweep(module, cycles, seed, output, register):
    rng = random.Random(seed)
    if module == 'VAGQEntryTable':
        from .entrytable.env import session
        from .entrytable.types import AddrPacket, DataPacket, Beat, SplitReq, StateUpdate
        async with session(output, register=register) as env:
            await env.reset()
            for sequence in range(max(1, cycles // 6)):
                index, lane = sequence % 8, sequence % 2
                rob = sequence % 512
                addr = AddrPacket(entry_idx=index, rob_value=rob, uop_type=sequence % 2,
                    vl=1, last_uop=1, base_addr=rng.getrandbits(40) << 3,
                    pdest=rng.randrange(128), psrc2=rng.randrange(128),
                    v0_mask=rng.getrandbits(16) | 1, vma=sequence % 2, vta=(sequence // 2) % 2)
                data = DataPacket(entry_idx=index, rob_value=rob, op2_data=rng.getrandbits(64))
                active = (True, False) if lane == 0 else (False, True)
                await env.step(Beat(addr=(addr, None) if lane == 0 else (None, addr), addr_valid=active,
                                    data=(data, None) if lane == 0 else (None, data), data_valid=active))
                await env.step(Beat(split_req=(SplitReq(True, 1 << index, 1), SplitReq())))
                await env.step(Beat(split_done=StateUpdate(True, 1 << index, 4)))
                await env.step(Beat(merge_done=StateUpdate(True, 1 << index, 5)))
                await env.step(Beat(rob_clear=StateUpdate(True, 1 << index, 0)))
                await env.step(Beat())
    elif module == 'OrderedPermitCtrl':
        from .ordered.env import session
        from .ordered.types import Beat, Entry, SplitDone
        async with session(output, register=register) as env:
            await env.reset()
            for sequence in range(max(1, cycles // 4)):
                first, second = sequence % 8, (sequence + 1) % 8
                rob, flag = rng.randrange(512), sequence % 2
                entries = [Entry() for _ in range(8)]
                entries[first] = Entry(True, 6, flag, rob, 0, False, False, 3)
                entries[second] = Entry(True, 6, flag, rob, 1, True, False, 3)
                await env.step(Beat(tuple(entries)))
                await env.step(Beat(tuple(entries), SplitDone(True, first)))
                entries[first] = Entry()
                await env.step(Beat(tuple(entries), SplitDone(True, second)))
                await env.step(Beat())
    elif module == 'VAGQ':
        from .native import open_dut
        from .vagq.env import Env
        from .vagq.types import AddrPacket, DataPacket, Beat
        from .vagq.driver import response_beat
        with open_dut(module, output, clocked=True, register=register) as dut:
            env = Env.create(dut)
            for sequence in range(max(1, cycles // 48)):
                env.reset()
                index = sequence % 8
                addr = AddrPacket(entry_idx=index, rob_value=sequence % 512, uop_type=0,
                    vl=1, last_uop=1, base_addr=rng.getrandbits(40) << 3,
                    pdest=rng.randrange(128), psrc2=rng.randrange(128),
                    v0_byte_mask=0xffff, deew=sequence % 4, vma=sequence % 2, vta=(sequence // 2) % 2)
                data = DataPacket(entry_idx=index, rob_value=addr.rob_value, op2_data=1 << addr.deew)
                beat = Beat(addr=(addr, None), addr_valid=(True, False),
                            stride=(data, None), stride_valid=(True, False))
                env.cycle(Beat())
                for tick in range(48):
                    observed = env.cycle(beat, admit=(addr, data) if tick == 0 else None)
                    if observed.get('io_robWriteback_valid'):
                        if observed['io_robWriteback_bits_entryIdx'] != index:
                            raise AssertionError('writeback does not belong to the admitted request')
                        break
                    beat = response_beat(observed, data=rng.getrandbits(128))
                else:
                    raise AssertionError('legal VAGQ sweep did not complete its admitted operation')
                env.finish()
    else:
        raise ValueError(f'no stateful structural contract for {module}')
