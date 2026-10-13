"""Kernel with interest on the extra interest (used by specs.objective)."""
from __future__ import annotations

from fractions import Fraction as Q


def kernel_iai(sc, wk, y, supports, perimeter):
    """Window kernel including interest, at rate y, on the extra interest itself (borrowed as it accrues).

    Extra debt at time t is the cumulated first-round cost; its interest in year k is approximated by
    y * (sum of earlier years' first-round cost + half of year k's). Still linear in the ledger.
    """
    from .model import kernel
    from .pa import PA
    y = Q(y)
    years = [1, 2, 3, 4, 5] if wk == "cum5" else [int(wk[1:])]
    total: dict = {}
    for k in years:
        parts = [((1 + y / 2), kernel(sc, k - 1, k, supports, perimeter))]
        for j in range(1, k):
            parts.append((y, kernel(sc, j - 1, j, supports, perimeter)))
        for w, kk in parts:
            for c, f in kk.items():
                g = f.scale(w)
                total[c] = total[c] + g if c in total else g
    return total


def kernel_recursive_annual(sc, wk, y, supports, perimeter):
    """Exact declared discrete convention, not continuous financing.

    Let C_k be first-round cost in year k, booked/borrowed at its midpoint.
    All previously accumulated extra debt pays simple annual rate y;
    C_k pays half-year interest. Thus B_k=(1+y)B_(k-1)+(1+y/2)C_k.
    Year-k interest cost is B_k-B_(k-1), with B_0=0. This includes
    interest on earlier financing interest, unlike kernel_iai.
    """
    from .model import kernel
    y = Q(y)
    if y < 0:
        raise ValueError('This implementation declares nonnegative financing rates')
    years = range(1, 6) if wk == 'cum5' else [int(wk[1:])]
    total = {}
    for k in years:
        for j in range(1, k + 1):
            weight = (1 + y/2) * (1 if j == k else y * (1+y)**(k-j-1))
            for c, f in kernel(sc, j-1, j, supports, perimeter).items():
                term = f.scale(weight)
                total[c] = total[c] + term if c in total else term
    return total
