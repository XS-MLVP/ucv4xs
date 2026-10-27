"""Address semantics independent of HDL layout and simulator APIs."""
from dataclasses import dataclass

U64 = (1 << 64) - 1


@dataclass(frozen=True, slots=True)
class AddressContext:
    base: int
    element: int
    offset: int
    data_bytes: int = 1
    first_field: int = 0

    def __post_init__(self):
        if not 0 <= self.base <= U64 or not 0 <= self.element < 128 or not 0 <= self.offset < 16:
            raise ValueError('address/element/offset outside RTL input domain')
        if self.data_bytes not in (1, 2, 4, 8) or not 0 <= self.first_field < 8:
            raise ValueError('invalid data size or field offset')


@dataclass(frozen=True, slots=True)
class StridedAddress:
    context: AddressContext
    stride: int

    def __post_init__(self):
        if not -(1 << 63) <= self.stride <= U64:
            raise ValueError('stride outside 64-bit encoding domain')


@dataclass(frozen=True, slots=True)
class IndexedAddress:
    context: AddressContext
    indices: tuple[int, ...]

    def __post_init__(self):
        if not isinstance(self.indices, tuple) or len(self.indices) not in (2, 4, 8, 16):
            raise ValueError('indices must exactly fill one 128-bit input')
        width = 128 // len(self.indices)
        if any(not 0 <= index < 1 << width for index in self.indices):
            raise ValueError('index does not fit its unsigned element width')


def address(request):
    ctx = request.context
    if isinstance(request, StridedAddress):
        displacement = request.stride * (ctx.element + ctx.offset)
    else:
        displacement = request.indices[(ctx.element + ctx.offset) % len(request.indices)]
    field = ctx.first_field * ctx.data_bytes if ctx.offset == 0 else 0
    return (ctx.base + displacement + field) % (1 << 64)
