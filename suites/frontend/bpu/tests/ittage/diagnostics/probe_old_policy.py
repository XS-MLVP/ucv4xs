"""Diagnostic only: reproduce the pre-fix reference policy, not a DUT verdict."""
from unittest.mock import patch

from bpuverify.ittage.model.semantic import Context, Events, IttageReference, Metadata, Outcome

PC, A = 0x40000800, 0x40002000


def test_pre_fix_reference_treated_an_unpublished_snapshot_as_learnable():
    """Before the qualification fix, the model ignored the master publication bit.

    This is the false-negative that made the original probe PASS while the DUT
    learned from residue. It is a diagnostic of the old policy, not a hardware
    PASS and not part of the production collection.
    """

    old_qualified = property(
        lambda self: self.valid and self.taken and self.indirect and not self.returns
    )
    feedback = Outcome(PC, Context(), Metadata(allocation=0, published=False), A,
                       mispredict=True)
    with patch.object(Outcome, 'qualified', old_qualified):
        model = IttageReference()
        assert feedback.qualified
        model.advance(Events(feedback=feedback))
        for _ in range(4):
            model.advance(Events())
        prediction = model.inspect(PC)
        assert prediction.provider == 0
        assert prediction.target == A
