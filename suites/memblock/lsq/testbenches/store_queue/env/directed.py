

async def consume(env, expected, end, *, credits=None, **controls):
    expected = list(expected)
    transferred = credit_sum = quiet = 0
    for _ in range(180):
        await env.cycle(sbuffer_ready=(True, True), **controls)
        for lane in range(2):
            issued = env.pre_response.sbuffer_word_0 if lane == 0 else env.pre_response.sbuffer_word_1
            if issued is not None:
                assert transferred < len(expected), "extra real StoreQueue write"
                va, pa, mask, data = expected[transferred]
                env.expect_sbuffer_word(lane, _word(va, pa, mask, data), "real StoreQueue source bytes",
                                        data_mask=sum(255 << (8 * byte) for byte in range(16) if mask >> byte & 1),
                                        before=True)
                transferred += 1
        credit_sum += env.pre_response.dequeue_count if env.pre_response.dequeue_valid else 0
        pointer = env.response.sq_deq_ptr
        position = int(pointer.first) * 128 + int(pointer.second) * 64 + pointer.value
        quiet = quiet + 1 if position == end % 256 and env.response.empty else 0
        if quiet == 5:
            break
    assert quiet == 5 and transferred == len(expected) and credit_sum == (len(expected) if credits is None else credits), (quiet, transferred, credit_sum)
    env.expect(_observation(empty=1, dequeue_valid=0, sbuffer_word_0=None, sbuffer_word_1=None),
               "real PSQ consumption/release feeds back into real VSQ retirement and combined empty")


def _word(va, pa, mask, data, *, wline=0):
    from suites.memblock.lsq.testbenches.shared.transactions import SbufferWord
    return SbufferWord(1, pa, va, mask, data, wline)


def _observation(**fields):
    from suites.memblock.lsq.testbenches.store_queue.transactions import Observation
    return Observation(**fields)
