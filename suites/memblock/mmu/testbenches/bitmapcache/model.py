"""BC-02 bitmap-word byte selection, independent of DUT observations."""


def selected_byte(word: int, index: int) -> int:
    return (word >> (8 * index)) & 0xFF
