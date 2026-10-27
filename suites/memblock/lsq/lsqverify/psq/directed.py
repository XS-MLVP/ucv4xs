"""Public directed helpers, not a full parent cycle reference."""
from .checks import check_word, ptr_values, read_ptr


def scalar_word(address, data):
    length = 1 << min(address.size, 4)
    offset = address.vaddr % 16
    assert offset + length <= 16
    return (address.vaddr // 16 * 16, address.paddr // 16 * 16,
            ((1 << length) - 1) << offset, data.data << (8 * offset) & ((1 << 128) - 1))


async def consume_writes(env, expected, target, *, credits=None, **permission):
    expected = list(expected)
    wanted_credits = len(expected) if credits is None else credits
    consumed = credit_sum = quiet = 0
    for _ in range(160):
        await env.cycle(sbuffer_ready=(True, True), **permission)
        for lane in range(2):
            if env.pre_observed[f"io_writeToSbuffer_req_{lane}_valid"]:
                assert consumed < len(expected), "unexpected real Sbuffer transfer"
                check_word(env, lane, *expected[consumed], before=True)
                consumed += 1
        credit_sum += env.pre_observed["io_sqDeq_bits"] if env.pre_observed["io_sqDeq_valid"] else 0
        quiet = quiet + 1 if read_ptr(env.observed) == target % 256 else 0
        if quiet == 4:
            break
    assert quiet == 4 and consumed == len(expected) and credit_sum == wanted_credits, (quiet, consumed, credit_sum, wanted_credits)
    env.expect({**ptr_values("io_sqDeqPtr_", target), "io_writeToSbuffer_req_0_valid": 0, "io_writeToSbuffer_req_1_valid": 0}, "all directed owners completed through real transfers and SQ credits")
