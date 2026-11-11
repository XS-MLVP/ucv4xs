"""Protocol controls use independent caller data and actual accepted transfers."""
import dataclasses

import pytest

from suites.memblock.dcache.testbenches.shared.env.execution import step


def test_two_pending_channels_are_serviced_without_losing_an_acquire(cache_protocol_env):
    env=cache_protocol_env
    addresses=(0x48000,0x48040)
    payloads=((0x1111,0x2222),(0x3333,0x4444))
    for lane,address in enumerate(addresses):
        response=env.load_once(lane,address,address)
        assert response['miss']==1 and response['handled']==1
    for index,address in enumerate(addresses):
        accepted=env.service_miss(address,data_beats=payloads[index])
        assert accepted['channel']==index and accepted['opcode']==6
        trace=env.last_refill
        assert [beat.data for beat in trace.grants]==list(payloads[index])
        assert all(beat.source==accepted['source'] for beat in trace.grants)
    step(env,8)
    for lane,address in enumerate(addresses):
        response=env.load_once(lane,address,address)
        assert response['miss']==0
        assert response['data']&((1<<64)-1)==payloads[lane][0]


def test_full_line_store_accepts_a_single_no_data_grant(cache_protocol_env):
    env=cache_protocol_env
    base=0x4A000
    data=bytes((index*7+3)&255 for index in range(64))
    env.drive_store(base,base,int.from_bytes(data,'little'),(1<<64)-1,store_id=7)
    accepted=env.service_miss(base,grant_data=False)
    env.stop_store()
    assert accepted['opcode']==7
    assert len(env.last_refill.grants)==1 and env.last_refill.grants[0].opcode==4
    response=env.wait_store_hit(16)
    assert response['hit']==1 and response['hit_id']==7
    step(env,8)
    # Read both halves of the 64B line, not only its first word.
    for offset in (0,8,24,32,40,56):
        response=env.load_once(0,base+offset,base+offset)
        assert response['miss']==0
        actual=(response['data']>>(8*(offset&15)))&((1<<64)-1)
        assert actual==int.from_bytes(data[offset:offset+8],'little'),(offset,response)


# ---------------------------------------------------------------- selftest
@pytest.mark.selftest
def test_release_ack_requires_complete_accepted_message():
    """Release completion identity: accepted-only, ack-once, env-scoped.

    The fake signals below are local to this selftest so the native attribute
    and clock edge stay visible in the classified scope; the methods under test
    are the real DcacheEnv release helpers.
    """
    from types import SimpleNamespace

    from suites.memblock.dcache.testbenches.dcache.env import DcacheEnv
    from suites.memblock.dcache.testbenches.dcache.env import ReleaseBeat

    class FakeSignal:
        def __init__(self, value=0):
            self.value = value

        def Set(self, value):
            self.value = value

    def harness(opcodes=(7, 6), valid=(1, 0), ready=(1, 1), *,
                param=1, data=(0x11, 0x22), d_ready=1, missing=(),
                second_beat=True, bubble=False):
        channels = []
        for index, opcode in enumerate(opcodes):
            channel = {
                "c_valid": FakeSignal(valid[index]),
                "c_ready": FakeSignal(ready[index]),
                "c_opcode": FakeSignal(opcode),
                "c_param": FakeSignal(param),
                "c_size": FakeSignal(6),
                "c_source": FakeSignal(3 + index),
                "c_address": FakeSignal(0x8000 + 64 * index),
                "c_data": FakeSignal(data[0]),
                "d_valid": FakeSignal(0),
                "d_ready": FakeSignal(d_ready),
                "d_opcode": FakeSignal(0),
                "d_size": FakeSignal(0),
                "d_source": FakeSignal(0),
                "d_sink": FakeSignal(0),
                "d_denied": FakeSignal(0),
                "d_corrupt": FakeSignal(0),
                "d_data": FakeSignal(0),
            }
            for name in missing:
                channel.pop(name)
            channels.append(channel)
        events, completed, pending = [], [0, 0], [0, 0]

        def step(count=1):
            for _ in range(count):
                fires = []
                for index, channel in enumerate(channels):
                    if channel["d_valid"].value and channel["d_ready"].value:
                        fires.append(("D", index, completed[index]))
                    if channel["c_valid"].value and channel["c_ready"].value:
                        completed[index] += 1
                        fires.append(("C", index, completed[index]))
                        count_beats = 2 if channel["c_opcode"].value == 7 else 1
                        if completed[index] >= count_beats:
                            channel["c_valid"].value = 0
                        elif not second_beat:
                            channel["c_valid"].value = 0
                        elif bubble and completed[index] == 1:
                            # One legal zero-valid bubble before the last beat.
                            channel["c_valid"].value = 0
                            pending[index] = 1
                        elif channel["c_opcode"].value == 7:
                            channel["c_data"].value = data[min(completed[index],
                                                               len(data) - 1)]
                    elif channel["c_valid"].value == 0 and pending[index]:
                        pending[index] -= 1
                        if not pending[index] and second_beat:
                            channel["c_valid"].value = 1
                events.append(fires)

        env = DcacheEnv.__new__(DcacheEnv)
        env.channels = channels
        env.refresh = lambda: None
        env.dut = SimpleNamespace(Step=step)
        return env, events, completed

    # ReleaseData needs both C beats before any D acknowledgement.
    env, events, completed = harness(opcodes=(7, 6), valid=(1, 0))
    message = env.wait_release(6)
    assert message is not None and message.opcode == 7
    assert len(message.beats) == 2 and completed[0] == 2
    assert all(not any(kind == "D" for kind, _, _ in cycle) for cycle in events)
    # Retry of the original object is allowed until an ACK edge completes.
    env.channels[0]["d_ready"].Set(0)
    with pytest.raises(AssertionError):
        env.acknowledge_release(message, limit=2)
    assert all(not any(kind == "D" for kind, _, _ in cycle) for cycle in events)
    env.channels[0]["d_ready"].Set(1)
    assert env.acknowledge_release(message)
    assert events[-1] == [("D", 0, 2)], events[-1]
    with pytest.raises(AssertionError):
        env.acknowledge_release(message)
    with pytest.raises(TypeError):
        env.acknowledge_release(ReleaseBeat(0, 6, 6, 3, 0x8000))

    # A legal inter-beat bubble is waited out inside the same budget.
    env, events, completed = harness(opcodes=(7, 6), valid=(1, 0), bubble=True)
    bubbled = env.wait_release(8)
    assert bubbled is not None and len(bubbled.beats) == 2, bubbled
    assert completed[0] == 2
    assert env.acknowledge_release(bubbled)

    # A message that never completes must fail, not return a zero-filled success.
    env, events, completed = harness(opcodes=(7, 6), valid=(1, 0),
                                     second_beat=False)
    with pytest.raises(AssertionError):
        env.wait_release(4)
    assert completed[0] == 1
    assert all(not any(kind == "D" for kind, _, _ in cycle) for cycle in events)

    # A backpressured observation is not an accepted message and cannot ACK.
    env, events, completed = harness(opcodes=(6, 6), valid=(1, 0),
                                     ready=(0, 0))
    assert env.wait_release(3) is None
    observed = env.observe_release(1)
    assert observed and completed == [0, 0]
    assert all(not cycle for cycle in events), events
    with pytest.raises(TypeError):
        env.acknowledge_release(observed[0])
    with pytest.raises(TypeError):
        env.acknowledge_release(None)

    # Both channels valid+ready in one cycle: only the selected channel fires.
    env, events, completed = harness(opcodes=(6, 6), valid=(1, 1))
    first = env.wait_release(4)
    assert first is not None and first.channel == 0
    assert events[0] == [("C", 0, 1)], events[0]
    assert completed == [1, 0] and env.channels[1]["c_valid"].value == 1
    assert env.acknowledge_release(first)
    second = env.wait_release(4)
    assert second is not None and second.channel == 1
    assert env.acknowledge_release(second)

    # Two environments can accept byte-identical releases (same header, data,
    # token 1, generation 0) and each still owns only its own message object.
    other, other_events, other_completed = harness(opcodes=(6, 6), valid=(1, 0))
    foreign = other.wait_release(4)
    assert foreign is not None and other_completed == [1, 0]
    env, events, completed = harness(opcodes=(6, 6), valid=(1, 0))
    own = env.wait_release(4)
    assert own is not None and completed == [1, 0]
    assert own == foreign and own is not foreign
    before = [channel["d_valid"].value for channel in env.channels]
    with pytest.raises(AssertionError):
        env.acknowledge_release(foreign)
    with pytest.raises(AssertionError):
        env.acknowledge_release(dataclasses.replace(own))
    assert [channel["d_valid"].value for channel in env.channels] == before, \
        "foreign or copied messages must not drive the D channel"
    assert env.acknowledge_release(own)

    # A forged message that reuses a real token is rejected before D is driven.
    env, events, completed = harness(opcodes=(6, 6), valid=(1, 0))
    accepted = env.wait_release(4)
    assert accepted is not None
    before = [channel["d_valid"].value for channel in env.channels]
    wrong_source = dataclasses.replace(
        accepted, beat=dataclasses.replace(accepted.beat, source=accepted.source + 1))
    with pytest.raises(AssertionError):
        env.acknowledge_release(wrong_source)
    stale_generation = dataclasses.replace(
        accepted, generation=accepted.generation + 1)
    with pytest.raises(AssertionError):
        env.acknowledge_release(stale_generation)
    wrong_channel = dataclasses.replace(
        accepted, beat=dataclasses.replace(accepted.beat, channel=1 - accepted.channel))
    with pytest.raises(AssertionError):
        env.acknowledge_release(wrong_channel)
    assert [channel["d_valid"].value for channel in env.channels] == before, \
        "rejected messages must not drive the D channel"
    assert env.acknowledge_release(accepted)

    # Port-indexed scalar observations reject negative/non-int lanes instead of
    # silently selecting a slot at the end of the list.
    lanes = DcacheEnv.__new__(DcacheEnv)
    lanes.loads = [{"req_ready": FakeSignal(1), "s2_mq_nack": FakeSignal(0)}
                   for _ in range(3)]
    for bad in (-1, 3, 0.5, "1"):
        with pytest.raises(ValueError):
            lanes.load_accept_ready(bad)
        with pytest.raises(ValueError):
            lanes.load_nack_pulse(bad)
    assert lanes.load_accept_ready(2) and not lanes.load_nack_pulse(0)

    # Required C fields must be bound; a missing field is not an observation of
    # zero.  ReleaseData needs c_data, every release needs c_param, and a
    # no-data Release must not consult c_data at all.
    env, events, completed = harness(opcodes=(7, 6), valid=(1, 0),
                                     missing=("c_data",))
    with pytest.raises(AssertionError):
        env.wait_release(4)
    assert completed == [0, 0]
    env, events, completed = harness(opcodes=(6, 6), valid=(1, 0),
                                     missing=("c_param",))
    with pytest.raises(AssertionError):
        env.wait_release(4)
    assert completed == [0, 0]
    env, events, completed = harness(opcodes=(6, 6), valid=(1, 0),
                                     missing=("c_data",))
    clean = env.wait_release(4)
    assert clean is not None and clean.opcode == 6 and clean.beats == ()
    assert env.acknowledge_release(clean)
