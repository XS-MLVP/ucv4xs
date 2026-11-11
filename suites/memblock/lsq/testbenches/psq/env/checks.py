from suites.memblock.lsq.testbenches.raw.transactions import SqPtr


def ptr_values(prefix, position):
    ptr = SqPtr.encode(position)
    return {prefix + "first_flag": int(ptr.first), prefix + "second_flag": int(ptr.second), prefix + "value": ptr.value}


def read_ptr(pins, prefix="io_sqDeqPtr_"):
    return pins[prefix + "first_flag"] * 128 + pins[prefix + "second_flag"] * 64 + pins[prefix + "value"]


def check_word(env, lane, va, pa, mask, data, *, wline=0, before=False):
    from suites.memblock.lsq.testbenches.shared.transactions import SbufferWord
    byte_mask = sum(255 << (8 * byte) for byte in range(16) if mask >> byte & 1)
    env.expect_sbuffer_word(lane, SbufferWord(1, pa, va, mask, data, wline),
                            "real PSQ source bytes and control at Sbuffer",
                            bit_masks={f"io_writeToSbuffer_req_{lane}_bits_data": byte_mask}, before=before)
