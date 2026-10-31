from suites.memblock.lsq.raw.types import SqPtr


def ptr_values(prefix, position):
    ptr = SqPtr.encode(position)
    return {prefix + "first_flag": int(ptr.first), prefix + "second_flag": int(ptr.second), prefix + "value": ptr.value}


def read_ptr(pins, prefix="io_sqDeqPtr_"):
    return pins[prefix + "first_flag"] * 128 + pins[prefix + "second_flag"] * 64 + pins[prefix + "value"]


def check_word(env, lane, va, pa, mask, data, *, wline=0, before=False):
    prefix = f"io_writeToSbuffer_req_{lane}_"
    env.expect({prefix + "valid": 1, prefix + "bits_vaddr": va, prefix + "bits_addr": pa, prefix + "bits_mask": mask,
                prefix + "bits_data": data, prefix + "bits_wline": wline}, "real PSQ source bytes and control at Sbuffer",
               before=before, bit_masks={prefix + "bits_data": sum(255 << (8 * byte) for byte in range(16) if mask >> byte & 1)})
