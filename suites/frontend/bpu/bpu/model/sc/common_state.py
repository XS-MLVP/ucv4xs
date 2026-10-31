"""suites.frontend.bpu.bpu.model.sc.common_state components."""




def dedup(mask, positions):
    seen, result = set(), []
    for hit, position in zip(mask, positions, strict=True):
        result.append(int(bool(hit) and position not in seen))
        if hit:
            seen.add(position)
    return result


def shifted(old, less, hits, taken, conditional, bit, width):
    shift = less if taken else hits
    value = old << shift
    if taken and conditional:
        value = (value << 1) | bit
    return value & ((1 << width) - 1)


def backwards(pc, target):
    # CommonHR.Helpers compares the elaborated MainBTB target's low 20 bits.
    return int((pc & ((1 << 20) - 1)) > (target & ((1 << 20) - 1)))


def update(state, positions, hits, prediction, selected):
    taken, conditional = prediction['taken'], prediction['branch_type'] == 1
    count = sum(hits)
    less = sum(hit and position < positions[selected] for hit, position in zip(hits, positions, strict=True)) if taken else 0
    cfi_pc = (prediction['pc'] & ~7) + prediction['position']
    return dict(valid=1,
        ghr=shifted(state['ghr'], less, count, taken, conditional, taken, 8),
        bw=shifted(state['bw'], less, count, taken, conditional,
            taken & conditional & backwards(cfi_pc, prediction['target']), 4))


def recovery(redirect):
    meta, position = redirect['meta'], redirect['cfi_pc'] & 15
    # The actual r1 path counts captured hits (not the debug-only dedup path).
    less = sum(hit and old < position for hit, old in zip(meta['hits'], meta['positions'], strict=True))
    taken, conditional = redirect['taken'], redirect['branch_type'] == 1
    return dict(valid=0,
        ghr=shifted(meta['ghr'], less, sum(meta['hits']), taken, conditional, taken, 8),
        bw=shifted(meta['bw'], less, sum(meta['hits']), taken, conditional,
            taken & backwards(redirect['cfi_pc'], redirect['target']), 4))
