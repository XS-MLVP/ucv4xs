"""Reference PLRU model for ICacheReplacer.

Semantics follow the published tree-PLRU algorithm used by RISC-V cores
(rocket-chip ``PseudoLRU``, documented at
https://en.wikipedia.org/wiki/Pseudo-LRU#Tree-PLRU, and Section 2.3 of
"Cache Replacement Policies" by Jain & Lin): each tree node stores one bit that
names the *older* subtree, a victim lookup follows the older pointers to a leaf,
and a touch inverts every node on the path to that leaf.

ICacheReplacer adds three things on top of that policy, and those are what its
functional points target:

* one independent PLRU instance per fetch port, selected by the low bit of
  ``vSetIdx`` (``PortNumber == 2``), with the remaining bits as the set index;
* two touch ports per instance, applied in port order (later port wins);
* the victim of cycle *N* is fed back as a touch in cycle *N+1*.
"""

from __future__ import annotations


def tree_ways(num_ways: int) -> int:
    """Number of state bits in a tree-PLRU for ``num_ways`` ways."""
    return max(0, num_ways - 1)


def _ceil_log2(value: int) -> int:
    return max(0, (value - 1).bit_length())


def _split(num_ways: int) -> tuple[int, int]:
    right = 1 << (_ceil_log2(num_ways) - 1)
    return num_ways - right, right


def _subtree_state(state: int, num_ways: int, right_ways: int) -> tuple[int, int]:
    """Split the node state into (left subtree state, right subtree state).

    Mirrors the published indexing: ``state[num_ways-2]`` names the older
    subtree, the left child occupies the bits above ``right_ways-1`` and the
    right child the low ``right_ways-1`` bits.
    """
    left_width = max(0, num_ways - 1 - right_ways)
    left_state = (state >> (right_ways - 1)) & ((1 << left_width) - 1)
    right_state = state & ((1 << max(0, right_ways - 1)) - 1)
    return left_state, right_state


def get_victim(state: int, num_ways: int) -> int:
    """Way selected by the older-pointer walk from the root."""
    if num_ways <= 1:
        return 0
    if num_ways == 2:
        return state & 1
    left_ways, right_ways = _split(num_ways)
    left_older = (state >> (num_ways - 2)) & 1
    left_state, right_state = _subtree_state(state, num_ways, right_ways)
    # The published tree numbers the *left* (older-bit=1) subtree with the
    # higher way indices: for 4 ways, state[1] compares way 3 against way 2 and
    # state[0] compares way 1 against way 0. So the left child owns ways
    # [right_ways .. num_ways) and the right child ways [0 .. right_ways).
    if left_older:
        return right_ways + get_victim(left_state, left_ways)
    return get_victim(right_state, right_ways)


def get_next_state(state: int, touch_way: int, num_ways: int) -> int:
    """Mark ``touch_way`` as newer along the whole root-to-leaf path."""
    if num_ways <= 2:
        # A two-way node stores the older way: touching one makes the other
        # older, i.e. the stored bit is the complement of the touched index.
        return (touch_way & 1) ^ 1
    left_ways, right_ways = _split(num_ways)
    left_state, right_state = _subtree_state(state, num_ways, right_ways)
    # The left (high-numbered) subtree is the one whose lane bit is 1, so a
    # touch in the low ways leaves the left subtree *older*.
    touched_left = touch_way >= right_ways
    set_left_older = 0 if touched_left else 1

    if left_ways > 1:
        new_left = left_state if set_left_older else get_next_state(
            left_state, (touch_way - right_ways) & ((1 << _ceil_log2(left_ways)) - 1), left_ways)
    else:
        new_left = 0
    if right_ways > 1:
        # When the touch went left the right subtree is entirely older, so its
        # stored older pointer is still the victim: keep it unchanged.
        new_right = right_state if not set_left_older else get_next_state(
            right_state, touch_way & ((1 << _ceil_log2(right_ways)) - 1), right_ways)
    else:
        new_right = right_state

    result = new_right & ((1 << max(0, right_ways - 1)) - 1)
    result |= (new_left & ((1 << max(0, left_ways - 1)) - 1)) << max(0, right_ways - 1)
    result |= set_left_older << (num_ways - 2)
    return result


class PortPlru:
    """One PLRU instance: dense per-set state plus the victim feedback latch."""

    def __init__(self, num_sets: int, num_ways: int) -> None:
        if num_sets <= 0 or num_ways < 1:
            raise ValueError("PLRU needs positive sets and ways")
        self.num_sets = num_sets
        self.num_ways = num_ways
        self.width = tree_ways(num_ways)
        self.state = [0] * num_sets
        # Victim latched last cycle; replayed as a touch on the next edge.
        self.pending_victim: int | None = None

    def victim(self, set_index: int) -> int:
        if not 0 <= set_index < self.num_sets:
            raise IndexError(f"set {set_index} outside 0..{self.num_sets - 1}")
        return get_victim(self.state[set_index], self.num_ways)

    def touch(self, set_index: int, way: int) -> None:
        if not 0 <= set_index < self.num_sets:
            raise IndexError(f"set {set_index} outside 0..{self.num_sets - 1}")
        if not 0 <= way < self.num_ways:
            raise IndexError(f"way {way} outside 0..{self.num_ways - 1}")
        self.state[set_index] = get_next_state(self.state[set_index], way, self.num_ways)

    def step(self, touches: tuple[tuple[int, int], ...]) -> None:
        """Advance one edge: feedback victim first, then this cycle's touches."""
        if self.pending_victim is not None:
            set_index, way = self.pending_victim
            self.touch(set_index, way)
        for set_index, way in touches:
            self.touch(set_index, way)


class ReplacerModel:
    """Two-port ICache replacer: one PLRU instance per fetch port."""

    def __init__(self, num_sets: int = 256, num_ways: int = 4, ports: int = 2) -> None:
        self.num_sets = num_sets
        self.num_ways = num_ways
        self.ports = ports
        self.sets_per_port = num_sets // ports
        self.instances = [PortPlru(self.sets_per_port, num_ways) for _ in range(ports)]

    # -- address decomposition, from the published port-interleave rule ------
    def port_of(self, vset_idx: int) -> int:
        return vset_idx & (self.ports - 1)

    def set_of(self, vset_idx: int) -> int:
        return (vset_idx >> 1) & (self.sets_per_port - 1)

    def victim(self, vset_idx: int) -> int:
        return self.instances[self.port_of(vset_idx)].victim(self.set_of(vset_idx))

    def step(
        self,
        *,
        touches: tuple[tuple[int, ...], ...],
        victim_request: int | None,
    ) -> None:
        """Advance one edge.

        ``touches[port]`` holds ``way`` per fetch request for that port, in
        application order; ``victim_request`` is the ``vSetIdx`` presented on
        the victim port this cycle, whose selected way becomes a touch on the
        next edge (the adapter latches it).
        """
        # The victim is combinational from the state *before* this edge's
        # touches, and the adapter latches exactly that value; compute it first.
        pending: tuple[int, int, int] | None = None
        if victim_request is not None:
            pending = (self.port_of(victim_request), self.set_of(victim_request),
                       self.victim(victim_request))

        for port, instance in enumerate(self.instances):
            # Touches arrive as (vSetIdx, way); the model stores per-port sets.
            applied = tuple(
                (self.set_of(vset_idx), way) for vset_idx, way in touches[port]
                if self.port_of(vset_idx) == port
            )
            instance.step(applied)
            instance.pending_victim = None

        if pending is not None:
            port, set_index, way = pending
            self.instances[port].pending_victim = (set_index, way)
