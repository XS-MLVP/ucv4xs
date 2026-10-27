"""Source S3 writeback relation; old frozen drivers stay unchanged.

No random calls or DUT/reference internal reads. Fixed-stage/public-effect
bookkeeping is inherited; only source-defined S3 metadata is corrected here.
"""
from dataclasses import replace

from .ldu_mixed_owners import LduMixedOwners
from .ldu_rar_owners import LduRarOwners


class LduS3MixedOwners(LduMixedOwners):
    @staticmethod
    def stage_writeback(item):
        # On actual uncache replay, S1 noQuery produces TlbAccessResult.noQuery,
        # NOT a new TLB hit. Final lqWrite.nc/mmio labels are not S2 isUncache.
        first_uncache = item["s"]["subtype"] != "cached" and not item["uncache_replay"]
        return bool(item["exceptions"] or item["match"] or
                    item["cause"] is None and not first_uncache)

    def plan(self, **options):
        packet,intent=super().plan(**options)
        loads=list(packet.loads)
        for lane,item in enumerate(intent["ldu_s3"]):
            if item is None or not loads[lane].execution.valid:continue
            head=item["s"]["head_s3"] if item["tail"] else None
            writeback=self.stage_writeback(item)
            if head is not None:
                always=bool(head["exceptions"] or head["match"])
                depends=self.stage_writeback(head) and not always
                writeback=always or depends and writeback
            loads[lane]=replace(loads[lane],update_address=writeback,
                                execution=replace(loads[lane].execution,aligned_type=item["size"],
                                                  last_beat=bool(loads[lane].paddr&64)))
        self._packet=replace(packet,loads=tuple(loads))
        return self._packet,intent


class LduS3RarOwners(LduRarOwners):
    async def pipeline(self, load, lane, **options):
        # This separate actor retains the documented aligned cached hit/nack
        # domain. The full NC/MMIO/S4 relation belongs to LduS3MixedOwners.
        size=(load.execution.uop.operation>>1)&7
        assert not load.mmio and not load.execution.nc and load.execution.mask==255 and size==3
        source=replace(load,execution=replace(load.execution,aligned_type=size,last_beat=bool(load.paddr&64)),
                       update_address=options.get("cause") is None)
        return await super().pipeline(source,lane,**options)
