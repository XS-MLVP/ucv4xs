"""Original-snapshot qualification, independent of a native DUT."""
from suites.frontend.bpu.ittage.model.semantic import Context, Events, IttageReference, Metadata, Outcome

PC, A = 0x40000800, 0x40002000


def test_unpublished_snapshot_cannot_qualify_late_feedback():
    model = IttageReference()
    feedback = Outcome(PC, Context(), Metadata(allocation=0, published=False), A,
                       mispredict=True)
    assert not feedback.qualified
    model.advance(Events(feedback=feedback))
    for _ in range(4):
        model.advance(Events())
    prediction = model.inspect(PC)
    assert prediction.provider is None
    assert model.commits == 0


def test_published_control_snapshot_still_learns_the_complete_target():
    model = IttageReference()
    feedback = Outcome(PC, Context(), Metadata(allocation=0), A, mispredict=True)
    assert feedback.qualified
    model.advance(Events(feedback=feedback))
    for _ in range(4):
        model.advance(Events())
    prediction = model.inspect(PC)
    assert (prediction.provider, prediction.confidence, prediction.target) == (0, 2, A)
