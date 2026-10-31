"""suites.frontend.bpu.abtb.case.state.replacer components."""




def packed(states):
    return f'{sum(value << (3 * index) for index, value in enumerate(states)):048x}'


def compact(row):
    return dict(tick=row['tick'], reset=row['reset'], banks=[dict(port,
        states=packed(port['states']), shadow=packed(port['shadow'])) for port in row['banks']])
