#!/usr/bin/env python3
"""Static normal-CBO input adapter check, NOT Picker/native functionality."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

from audit_sq_initial import ROOT, sha

sys.path.insert(0,str(ROOT/"tests"))
from lsq_wrapper.normal_owners import NormalCboStore
from lsq_wrapper.special_owners import SpecialStore
from suites.memblock.lsq.lsq_wrapper.codec import encode, load_public_view, store_public_view
from suites.memblock.lsq.lsq_wrapper.types import Address, Data, Inputs
from suites.memblock.lsq.vlq.types import RobPtr


def main():
    profiles=[]
    for opcode in range(4):
        for generation in range(4):
            for offset in (0,16,32,48):
                original=SpecialStore(generation*64+7,RobPtr.encode(11),0x10003+offset,0xA100003+offset,
                                      size=3,value=0x112233445566778899AABBCCDDEEFF00,cbo=opcode)
                owner=NormalCboStore.from_interface(original)
                assert owner.rob==original.rob and owner.position==original.position and owner.value==original.value and owner.cbo==opcode
                assert (owner.size,owner.vaddr,owner.paddr)==(4,original.vaddr//16*16,original.paddr//16*16)
                assert owner.words()==([(owner.vaddr,owner.paddr,65535,0)] if opcode==3 else [])
                for lane in range(2):
                    for miss in (False,True):
                        aa,dd=[Address()]*2,[Data()]*2
                        aa[lane],dd[1-lane]=owner.address(miss=miss),owner.data()
                        inp=Inputs(addresses=tuple(aa),data=tuple(dd))
                        pins=encode(inp)
                        load,store=load_public_view(inp),store_public_view(inp)
                        a=store.addresses[lane]
                        assert (a.size,a.mask,a.wline,a.last,a.cross_word,a.tlb_miss)==(4,65535,True,True,False,miss)
                        raw=load.stores[lane]
                        assert (raw.paddr,raw.mask,raw.wline,raw.rob,raw.tlb_miss)==(owner.paddr,65535,True,owner.rob,miss)
                        assert len(pins)==603
                        profiles.append(dict(opcode=opcode,generation=generation,offset=offset,lane=lane,tlb_miss=miss,
                                             full603_input_sha256=hashlib.sha256(json.dumps(pins,sort_keys=True).encode()).hexdigest()))
    good=NormalCboStore.from_interface(SpecialStore(0,RobPtr.encode(1),0x10000,0xA100000,cbo=3))
    reject=0
    for fields in (dict(size=3),dict(memory=1),dict(cbo=None),dict(vaddr=0x10001),dict(paddr=0xA100001),dict(second_page=0xB100000)):
        try:replace(good,**fields)
        except (ValueError,TypeError):reject+=1
        else:raise AssertionError(("invalid normal CBO accepted",fields))
    try:good.address(tail=True)
    except ValueError:reject+=1
    else:raise AssertionError("normal CBO tail accepted")
    assert len(profiles)==256 and reject==7
    output=ROOT/"results/static/lsq-normal-cbo-v1"
    output.mkdir(parents=True,exist_ok=True)
    report=dict(status="STATIC_ONLY_256_normal_CBO_adapter_profiles_and_seven_invalid_packages_checked",profiles=profiles,positive_profiles=256,rejected=reject,
                source_sha256={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),ROOT/"tests/lsq_wrapper/normal_owners.py",ROOT/"tests/lsq_wrapper/special_owners.py",ROOT/"lsq_wrapper/codec.py")},
                limits="No native DUT run, functionality, coverage, normal full-domain random acceptance or STRESS checked claim. This opt-in new actor is not yet wired into current frozen/running mixed/joint stimuli. It preserves original UID/ROB/SQ/value/opcode but derives real StoreUnit aligned16/QB/fullmask/wline for BOTH SQ and RAW views. Legacy interface actors and all historical results remain untouched; real tests and full independent producer/lifecycle gates remain required.")
    file=output/"report.json"
    if file.exists():assert json.loads(file.read_text())==report
    else:file.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="profiles"},indent=2,ensure_ascii=False))


if __name__=="__main__":main()
