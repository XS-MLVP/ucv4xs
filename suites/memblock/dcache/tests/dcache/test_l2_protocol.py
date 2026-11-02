"""Protocol controls use independent caller data and actual accepted transfers."""
from suites.memblock.dcache.execution import step


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
