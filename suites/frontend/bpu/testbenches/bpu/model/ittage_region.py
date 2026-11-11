"""Three equal-offset target regions, in the integrated halfword convention."""
REGION_HALFWORD_BITS = 19  # RTL TargetWidth=20 byte-address bits, bit0 is pruned.
OFFSET = 0x90


def target_regions(pc):
    if type(pc) is not int or not 1 << REGION_HALFWORD_BITS <= pc < (1 << 49) - (1 << REGION_HALFWORD_BITS):
        raise ValueError('PC must allow representable previous and following regions')
    region = pc >> REGION_HALFWORD_BITS
    return tuple((value << REGION_HALFWORD_BITS) | OFFSET for value in (region, region + 1, region - 1))


def feedback_targets(pc):
    same, following, _ = target_regions(pc)
    # First establish the foreign region unconditionally. The alternating
    # prefix reaches the highest provider without selecting a literal LFSR
    # allocation table. Move it to the PC region, then back to the KNOWN
    # foreign region at confidence zero, with no new table allocation possible.
    return (following, same, following, *(same,) * 5, *(following,) * 6)


def directory_program():
    """Capacity, reuse and two replacements, not a physical-index sweep."""
    base, rows = 0x40010006, []
    pc_region = base >> REGION_HALFWORD_BITS
    intents = [('pc-region-control', pc_region, 0x90)]
    intents += [('fill', pc_region + 0x10 + i, 0x90) for i in range(16)]
    # The directory must prefer an existing region even while free entries remain.
    # This reuses pointer3 after eight fills; it is not another physical-index case.
    intents.insert(9, ('reuse-partial', pc_region + 0x13, 0x110))
    intents += [('reuse', pc_region + 0x17, 0x120),
        ('replace-first', pc_region + 0x30, 0x180), ('replace-second', pc_region + 0x31, 0x240)]
    for i, (role, region, offset) in enumerate(intents):
        rows.append(dict(pc=base + 8 * i, target=(region << REGION_HALFWORD_BITS) | offset,
            role=role, position=7))
    return rows


def allocation_rule(regions, pc, target):
    """Classify the qualified logical input, not an actual DUT write pointer."""
    region = target >> REGION_HALFWORD_BITS
    if region == pc >> REGION_HALFWORD_BITS:
        return 'pc-region-bypass'
    if region in regions:
        return 'reuse-before-full' if None in regions else 'reuse-at-full'
    return 'free-entry' if None in regions else 'PLRU-replacement'


def consumption_rule(resident, regions):
    if resident['pointer'] is None:
        return 'pc-region'
    return 'resident-pointer' if regions[resident['pointer']] == resident['input']['target'] >> REGION_HALFWORD_BITS else 'replaced-pointer'
