"""The two pipe roots run the same protocol scenarios with separate payload contracts."""
from vagqverify.pipeline.types import Beat, Pipe3Payload, PipePayload


def pipe1_payload(tag):
    return PipePayload(
        entry_idx=tag & 7, rob_flag=tag & 1, rob_value=0x100 + tag,
        is_load=tag & 1, lq_flag=(tag >> 1) & 1, lq_value=tag & 0x7f,
        sq_first_flag=(tag >> 2) & 1, sq_second_flag=(tag >> 3) & 1,
        sq_value=tag & 0x3f, elem_idx=tag & 0x7f, data_size=tag & 7,
        data_mask=(0x1111 * (tag + 1)) & 0xffff, pc=0x1000 + tag,
        ftq_flag=(tag >> 1) & 1, ftq_value=tag & 0x3f, ftq_offset=tag & 0x1f,
        byte_offset=tag & 0xf, vaddr=0x100000 + tag, pdest=tag & 0x7f,
    )


def pipe3_payload(tag):
    return Pipe3Payload(
        entry_idx=tag & 7, rob_flag=tag & 1, rob_value=0x100 + tag,
        is_load=tag & 1, lq_value=tag & 0x7f,
        sq_first_flag=(tag >> 2) & 1, sq_second_flag=(tag >> 3) & 1,
        sq_value=tag & 0x3f, issue_mask=(0x0101 * (tag + 1)) & 0xffff,
    )


async def exercise(env, payload):
    await env.reset()
    zero = payload(0)
    first = payload(1)
    second = payload(2)
    # Empty/idle and capture.
    await env.step(Beat(payload=zero))
    await env.step(Beat(in_valid=True, payload=first))
    # Full backpressure holds the first payload; out_ready alone does not consume.
    await env.step(Beat(in_valid=True, out_ready=False, payload=second))
    await env.step(Beat(out_ready=True, payload=second))
    # Explicit right-side consumption clears the slot.
    await env.step(Beat(right_out_fire=True, payload=second))
    # Replacement and flush priority.
    await env.step(Beat(in_valid=True, out_ready=True, right_out_fire=True, payload=second))
    await env.step(Beat(in_valid=True, out_ready=True, right_out_fire=True, is_flush=True, payload=first))
    # Empty slot can accept again after flush.
    await env.step(Beat(in_valid=True, payload=first))
    await env.step(Beat(right_out_fire=True, payload=first))


async def test_full_payload_pipe_contract(pipeline_env):
    await exercise(pipeline_env, pipe1_payload)
    pipeline_env.coverage.group.assert_coverage(100)
    assert pipeline_env.checker.board.status.failed == 0


async def test_compact_payload_pipe_contract(pipeline3_env):
    await exercise(pipeline3_env, pipe3_payload)
    pipeline3_env.coverage.group.assert_coverage(100)
    assert pipeline3_env.checker.board.status.failed == 0
