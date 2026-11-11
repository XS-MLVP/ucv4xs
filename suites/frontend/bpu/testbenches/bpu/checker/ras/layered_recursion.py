"""Compare the whole mixed-PC return chain, not only the final destination."""


def compare_returns(check, program, pcs, targets):
    check(program.return_pcs, tuple(pcs), phase='each-final-return-has-its-logical-owner-PC')
    check(program.return_targets, tuple(targets), phase='expanded-multilevel-return-address-sequence')
