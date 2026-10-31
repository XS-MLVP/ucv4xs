"""Legal high-address and exception payload transitions for one real entry."""

from dataclasses import replace

from suites.memblock.lsq.uncache_entry.types import SOURCE_EXCEPTION_MASK


async def test_high_address_and_fault_payload_bits_are_checked(entry):
    # All exported address/exception fields are legal at their full widths.
    # The entry model still owns the lifecycle and checks the actual public
    # request, response, wakeup, data and exception observations.
    high = replace(
        entry.request(nc=True, tag=0x155, lq=127),
        vaddr=(1 << 50) - 1,
        fullva=(1 << 64) - 1,
        paddr=(1 << 48) - 1,
        gpaddr=(1 << 64) - 1,
        exceptions=SOURCE_EXCEPTION_MASK,
    )
    await entry.cycle(high, pending=high.rob)
    await entry.complete(data=(1 << 64) - 1, sid=15, error=True, nderr=True)

    # A second legal owner with zero-valued addresses and no source exception
    # forces the stored fields and exception report back in the opposite
    # direction instead of relying on reset/random initialization.
    low = replace(
        entry.request(nc=False, tag=0, lq=0),
        vaddr=0,
        fullva=0,
        paddr=0,
        gpaddr=0,
        exceptions=0,
    )
    await entry.cycle(low, pending=low.rob)
    await entry.complete(data=0, sid=0, error=False, nderr=False)
