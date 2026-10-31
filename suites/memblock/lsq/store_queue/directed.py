from suites.memblock.lsq.psq.checks import check_word, read_ptr


async def consume(env, expected, end, *, credits=None, **controls):
    expected = list(expected)
    transferred = credit_sum = quiet = 0
    for _ in range(180):
        await env.cycle(sbuffer_ready=(True, True), **controls)
        for lane in range(2):
            if env.pre_observed[f"io_writeToSbuffer_req_{lane}_valid"]:
                assert transferred < len(expected), "extra real StoreQueue write"
                check_word(env, lane, *expected[transferred], before=True)
                transferred += 1
        if env.pre_observed["io_toLsqEnqCtrl_sqDeq_valid"]:
            credit_sum += env.pre_observed["io_toLsqEnqCtrl_sqDeq_bits"]
        quiet = quiet + 1 if read_ptr(env.observed) == end % 256 and env.observed["io_sqEmpty"] else 0
        if quiet == 5:
            break
    assert quiet == 5 and transferred == len(expected) and credit_sum == (len(expected) if credits is None else credits), (quiet, transferred, credit_sum)
    env.expect({"io_sqEmpty": 1, "io_toLsqEnqCtrl_sqDeq_valid": 0, "io_writeToSbuffer_req_0_valid": 0, "io_writeToSbuffer_req_1_valid": 0},
               "real PSQ consumption/release feeds back into real VSQ retirement and combined empty")
