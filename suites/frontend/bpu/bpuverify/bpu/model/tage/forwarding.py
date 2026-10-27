"""One logical two-conditional path, not a physical-coordinate matrix."""
PC=0x40000800
POSITIONS=(4,10)
TARGETS=(PC+0x200,PC+0x600)


def establish_program():
    """Intent plus hand-derived post-feedback counters (Main first, TAGE second).

    NT prefixes preserve execution order. TAGE is held only while preparing
    base confidence; both real providers are then learned in the longest
    history table, so later wrong outcomes cannot silently promote them.
    """
    # Discover the later branch first: discovering the earlier taken branch
    # then names that genuinely wrong position, not a later branch after an
    # already mispredicted taken prefix.
    yield 'resolve',((1,True,True),),None,((None,2),(None,None))
    yield 'resolve',((0,True,True),),None,((2,2),(None,None))
    yield 'disable',(),None,None
    yield 'resolve',((0,False,True),(1,False,False)),None,((1,1),(None,None))
    yield 'resolve',((0,False,False),(1,False,False)),None,((0,0),(None,None))
    yield 'resolve',((0,True,True),),None,((1,0),(None,None))
    yield 'resolve',((0,True,True),),None,((2,0),(None,None))
    yield 'enable',(),None,None
    yield 'allocate',((0,False,True),(1,False,False)),(3,0),((1,0),(3,None))
    yield 'allocate',((0,False,False),(1,True,True)),(3,1),((0,1),(2,4))
    yield 'resolve',((0,False,False),(1,True,True)),None,((0,2),(1,5))
    yield 'resolve',((0,True,True),),None,((1,2),(2,5))


def resolved_path():
    return ((0,False,False),(1,True,False))
