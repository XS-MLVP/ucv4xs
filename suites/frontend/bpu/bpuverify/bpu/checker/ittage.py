"""Compare defined metadata fields against an input-derived context."""
from toffee import CheckContext, ScoreboardMode


def defined_fields(actual, expected):
    return {key: defined_fields(actual[key], value) if isinstance(value, dict) else actual[key]
            for key, value in expected.items()}


def check_metadata(board, model, transaction, *, phase):
    expected = model.metadata()
    board.check(expected=expected,
        actual=defined_fields(transaction.meta.resolve['ittage'], expected),
        context=CheckContext(board.name, ScoreboardMode.DIRECT,
            request=dict(phase=phase, pc=transaction.prediction.start_pc,
                         expected_resident_entries=dict(model.entries)),
            sequence_id=transaction.meta_tick))


def check_coherent_target(board, checker, transaction, target, feedback_target, position, context):
    """Check the associated S3, not a second consumer of coherent streams."""
    rows = [row for row in checker.records if row['tick'] == transaction.meta_tick]
    board.check(expected=1, actual=len(rows), context=context)
    row, = rows
    board.check(expected=(transaction.prediction.start_pc, target, 1, position),
        actual=(row['parent']['s3_pc'], row['parent']['s3_target'], row['parent']['s3_taken'],
            row['boundary']['s3']['prediction']['position']), context=context)
    if target != feedback_target:
        board.check(expected=1, actual=row['boundary']['s3']['valid'], context=context)
