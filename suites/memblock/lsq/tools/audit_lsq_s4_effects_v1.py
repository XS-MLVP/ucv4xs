#!/usr/bin/env python3
"""Preserve frozen UID core, replace only its too-narrow fullva assertion.

Independent source gate provides exact S4 fullva; ordinary aligned assertion
stays. Replay source projects output fullva from its vaddr and clears input
exceptionVec, not the earlier fault-bearing S4 input fullva/vector.
"""
import ast
from copy import deepcopy
from hashlib import sha256
from inspect import getsource
from pathlib import Path

import audit_lsq_ldu_mixed_history_v1 as original
from audit_lsq_population_v1 import events, replay_metadata
from audit_lsq_s4_source_v1 import key


OLD='packet["fullva"]==q["vaddr"] and packet["paddr"]%4096==q["vaddr"]%4096'
NEW='packet["fullva"]==source_fullva(tick,packet) and packet["paddr"]%4096==q["vaddr"]%4096'


def inspect(path, *, passed, source_metadata):
    digest=sha256(Path(original.__file__).read_bytes()).hexdigest()
    assert digest=="8490d9a7c312a2597664ab996e0193bde4a61bc532fb20525e0b2d6d9a283934"
    tree=ast.parse(getsource(original.inspect))
    before=ast.dump(tree,include_attributes=False)
    old=ast.dump(ast.parse(OLD,mode="eval").body,include_attributes=False)
    matches=[n for n in ast.walk(tree) if isinstance(n,ast.Assert) and ast.dump(n.test,include_attributes=False)==old]
    assert len(matches)==1
    matches[0].test=ast.parse(NEW,mode="eval").body
    ast.fix_missing_locations(tree)
    after=ast.dump(tree,include_attributes=False)
    def source_fullva(tick,packet):
        k=key(tick,packet)
        if k in source_metadata:return source_metadata[k]["fullva"]
        e=packet["execution"]
        assert not(e["aligned_type"]==4 and e["uop"]["operation"]==6),"S4 requires separate independent source metadata"
        return e["vaddr"]
    def cleared_grant(pins,prefix,packet):
        packet=deepcopy(packet)
        packet["execution"]["uop"]["exceptions"]=0
        packet["fullva"]=packet["execution"]["vaddr"]
        return replay_metadata(pins,prefix,packet)
    namespace={**original.__dict__,"source_fullva":source_fullva,"replay_metadata":cleared_grant}
    exec(compile(tree,"<S4-specific-preserved-UID-core>","exec"),namespace)
    result=namespace["inspect"](path,passed=passed)
    result["preserved_core_proof"]=dict(original_file_SHA256=digest,single_AST_assert_replacement=True,old_assert=OLD,new_assert=NEW,
                                        before_AST_SHA256=sha256(before.encode()).hexdigest(),after_AST_SHA256=sha256(after.encode()).hexdigest(),
                                        replay_projection_rules="LoadQueueReplay.scala765 fullva:=replay_req_vaddr and875 zeroInit; other original metadata/effects/recovery assertions retained. Only a copied expected grant descriptor is projected; actual raw/S4 input not edited.")
    return result
