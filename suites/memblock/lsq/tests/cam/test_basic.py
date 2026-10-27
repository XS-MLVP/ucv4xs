"""First-pass CAM coverage: intentionally only a small portion of one bank."""
from lsqverify.cam.types import Write


async def test_basic_synchronous_write_and_query(cam):
    env = cam
    for address in range(3):
        value = 0x1234 + address
        queries = env.queries((value, 0xFFFF))
        await env.cycle({0: Write(address, value, True)}, queries)
        await env.idle(env.spec["write_delay"], queries)
    await env.probe_values()
    assert env.model.entries[:3] == [0x1234, 0x1235, 0x1236]


async def test_rewrite_visibility_and_disabled_payload(cam):
    env = cam
    for value in (0x3333, 0x5555, 0x7777):
        queries = env.queries((value, 0x3333))
        await env.cycle({0: Write(0, value, True)}, queries)
        await env.idle(env.spec["write_delay"], queries)
    poison = {i: Write(i, 0xFFFF - i, False) for i in range(3)}
    for _ in range(3):
        await env.cycle(poison, env.queries((0x7777, 0xFFFF)))
    await env.probe_values((0x3333, 0x5555, 0x7777))
    assert env.model.entries[0] == 0x7777
