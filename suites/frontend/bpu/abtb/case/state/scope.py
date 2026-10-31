"""Reject unsupported geometry before native binding or transactions."""


def bank_index(value):
    if type(value) is not int or not 0 <= value < 4:
        raise ValueError('AheadBTB bank must be an integer in [0,4)')
    return value


def physical_axis(values, *, size, name):
    values = tuple(values)
    if not values or any(type(value) is not int or not 0 <= value < size for value in values):
        raise ValueError(f'AheadBTB {name} must be a nonempty integer axis in [0,{size})')
    if len(values) != len(set(values)):
        raise ValueError(f'AheadBTB {name} must not contain duplicate values')
    return values


def set_axis(values):
    return physical_axis(values, size=64, name='sets')


def way_axis(values):
    return physical_axis(values, size=4, name='ways')


def order_axis(values):
    values = tuple(values)
    allowed = ('ascending', 'descending', 'interleaved', 'boundary')
    if not values or any(value not in allowed for value in values) or len(values) != len(set(values)):
        raise ValueError('AheadBTB set orders must be nonempty, unique supported names')
    return values
