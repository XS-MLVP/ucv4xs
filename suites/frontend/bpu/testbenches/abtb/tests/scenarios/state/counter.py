"""suites.frontend.bpu.testbenches.abtb.tests.scenarios.state.counter components."""




def packed(cells):
    return f'{sum(value<<(2*i) for i,value in enumerate(cells)):0512x}'
