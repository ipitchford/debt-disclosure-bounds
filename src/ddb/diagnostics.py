"""Exact, model-conditional identification and reporting-vector diagnostics."""
from .lp import bounds, check_certificate


def identification(prob):
    """Return certified endpoints; equality is a global test on the feasible set.

    Does not assume the realised portfolio's support was disclosed. Infeasible
    or unbounded programmes raise rather than being classified as identified.
    """
    lo, hi = bounds(prob)
    for b in (lo, hi):
        check_certificate(prob, b.sense, b.value, b.measure, b.dual)
    return {'identified': lo.value == hi.value, 'lower': lo, 'upper': hi}


def independent_disclosures(prob, candidate):
    """Linear rank increment over baseline equalities on a common full grid.

    This counts independent linear numbers, not collection cost. It does not
    exploit inequalities that become universally tight on a boundary face.
    Rounded conditional means are excluded: their coefficients depend on the
    reported value and cannot be ranked as fixed linear reporting vectors.
    """
    from fractions import Fraction as Q
    from flint import fmpq_mat, fmpq
    from .lp import Problem, _build
    if any(m.lo != m.hi for m in candidate):
        raise ValueError('Only exact linear reporting vectors have a rank count')
    combined = Problem(prob.supports, prob.objective, prob.moments+candidate, prob.couplings, prob.grid)
    cols, _, rows, _, _, _ = _build(combined)
    base = [rows[i] for i,m in enumerate(prob.moments) if m.lo is not None and m.lo == m.hi]
    extra = rows[len(prob.moments):len(prob.moments)+len(candidate)]
    def rank(rs):
        if not rs:
            return 0
        matrix = fmpq_mat(len(rs),len(cols))
        for i,row in enumerate(rs):
            for j,v in row.items():
                matrix[i,j] = fmpq(v.numerator,v.denominator)
        return matrix.rank()
    r = rank(base)
    return {'reported_scalars':len(candidate),'additional_linear_rank':rank(base+extra)-r,
            'baseline_rank':r,'quantity_names':[m.name for m in candidate]}
