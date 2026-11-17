"""NewPipelineConnectPipe_3 protocol scenarios with its own payload contract."""
from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.transactions import Beat
from suites.vector.vagq.testbenches.NewPipelineConnectPipe_3.transactions import Pipe3Payload


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


async def test_compact_payload_pipe_contract(pipeline3_env):
    await exercise(pipeline3_env, pipe3_payload)
    pipeline3_env.assert_coverage(100)
    pipeline3_env.assert_clean()
