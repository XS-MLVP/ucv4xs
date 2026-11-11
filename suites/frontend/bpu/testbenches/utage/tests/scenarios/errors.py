class UtageTagWidthMismatch(AssertionError):
    """Only a proved training/prediction tag-width mismatch, not prerequisites."""


class UtageUsefulProviderBlocked(AssertionError):
    """A completed update matrix has genuine providers blocked by UTAGE-007."""

