"""bpuverify.bpu.checker.sc.history_training components."""




class Checks:
    def __init__(self, *checkers):
        self.checkers = checkers

    def __getattr__(self, name):
        return getattr(self.checkers[0], name)

    def raise_failure(self):
        for checker in self.checkers:
            checker.raise_failure()
