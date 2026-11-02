"""Complete encoding from strict transactions, no readiness/oracle policy."""
from suites.frontend.icache.transactions.sram import encode_controls


def encode(cycle):
    read, write, bist = cycle.read, cycle.write, cycle.bist
    return dict(read=dict(valid=int(read is not None), setIdx=read.set_index if read else 0),
        write=dict(valid=int(write is not None), setIdx=write.set_index if write else 0,
            waymask=write.waymask if write else 0, phyTag=write.phy_tag if write else 0,
            maybeRvcMap=write.maybe_rvc_map if write else 0, code=write.code if write else 0),
        flush=dict(flushAll=cycle.flush_all),
        bist=dict(req=int(bist is not None), all=bist.all_arrays if bist else 0, array=bist.array if bist else 0,
            readen=bist.readen if bist else 0, writeen=bist.writeen if bist else 0, be=bist.be if bist else 0,
            addr=bist.addr if bist else 0, addr_rd=bist.addr_rd if bist else 0, indata=bist.indata if bist else 0),
        controls=encode_controls(cycle.controls) if cycle.controls is not None else None)
