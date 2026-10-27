"""Full original stream; explicit S4 tail TLB metadata, no random changes."""
from dataclasses import replace

from .ldu_s3_owners import LduS3MixedOwners


class LduS4MixedOwners(LduS3MixedOwners):
    def ticket(self, s, *, tail=False, uncache=False):
        item=super().ticket(s,tail=tail,uncache=uncache)
        load=s["load"]
        item["source_fullva"]=item["VA"] if tail else load.fullva
        item["source_gpaddr"]=load.gpaddr+item["PA"]-load.paddr
        item["source_nonleaf"],item["source_hyper"]=load.nonleaf,load.hyper
        if item["cross"] or tail:
            self.env.emit("S4_mixed_external_TLB_input_before_S0",uid=s["uid"],ROB_absolute=s["order"],tail=tail,
                          VA=item["VA"],PA=item["PA"],fullva=item["source_fullva"],gpaddr=item["source_gpaddr"],
                          nonleaf=item["source_nonleaf"],hyper=item["source_hyper"],
                          scope="chosen external continuous TLB policy, not native TLB/LoadUnit proof")
        return item

    def plan(self, **options):
        packet,intent=super().plan(**options)
        loads=list(packet.loads)
        for lane,item in enumerate(intent["ldu_s3"]):
            if item is None or not item["tail"] or not loads[lane].execution.valid:continue
            head=item["s"]["head_s3"]
            assert head is not None
            selected=head if head["exceptions"] else item
            fault=selected["exceptions"]
            loads[lane]=replace(loads[lane],exceptions=fault,fullva=selected["source_fullva"],gpaddr=selected["source_gpaddr"],
                                nonleaf=selected["source_nonleaf"],hyper=item["source_hyper"],
                                execution=replace(loads[lane].execution,uop=replace(loads[lane].execution.uop,exceptions=fault)))
        self._packet=replace(packet,loads=tuple(loads))
        return self._packet,intent
