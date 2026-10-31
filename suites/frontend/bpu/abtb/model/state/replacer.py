"""Independent four-way tree PLRU; no observed state feeds the reference."""


def touch(state, way):
    if not 0 <= state < 8 or not 0 <= way < 4:
        raise ValueError((state, way))
    root = 0 if way >= 2 else 1
    child_bit = 1 if way >= 2 else 0
    child = 0 if way & 1 else 1
    return ((state & ~(4 | (1 << child_bit)))
            | (root << 2) | (child << child_bit))


def victim(state):
    if not 0 <= state < 8:
        raise ValueError(state)
    pair = (state >> 2) & 1
    return (pair << 1) | ((state >> pair) & 1)


def update(states, port):
    """Both writers read old state; same-set write response wins outright."""
    result = list(states)
    if port['read_valid']:
        index = port['read_set']
        value = states[index]
        for way, valid in enumerate(port['read_mask']):
            if valid:
                value = touch(value, way)
        result[index] = value
    if port['write_valid']:
        index = port['write_set']
        result[index] = touch(states[index], port['write_way'])
    return result


def route(encoded_pc, path_hash):
    # The public port is PrunedAddr.addr, not the full byte-address UInt.
    index = ((encoded_pc << 1) ^ path_hash) & 255
    return index & 3, index >> 2
