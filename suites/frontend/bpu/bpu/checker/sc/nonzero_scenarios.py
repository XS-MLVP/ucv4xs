"""suites.frontend.bpu.bpu.checker.sc.nonzero_scenarios components."""




class Checks:
    def __init__(self, sc, *others):
        self.sc, self.others = sc, others

    def __getattr__(self, name):
        return getattr(self.sc, name)

    def raise_failure(self):
        self.sc.raise_failure()
        for checker in self.others:
            checker.raise_failure()
