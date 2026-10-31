"""Bounded normal-feedback direction epochs, independent of DUT signal mechanics."""
def direction_epochs(maximum_pairs):
    if type(maximum_pairs) is not int or maximum_pairs < 1:
        raise ValueError("maximum_pairs must be a positive integer")
    return tuple((("negative",1),("positive",2)) for _ in range(maximum_pairs))
