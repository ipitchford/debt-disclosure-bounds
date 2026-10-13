"""Closed-form sharp bounds for a single measure (code path C), used to cross-check the LP.

Window kernel for refixing at t, window [a, b):  g(t) = (b - t)^+ - (a - t)^+,  t in [0, M], 0 <= a < b <= M.
It equals b - a on [0, a], decreases with slope -1 on [a, b], and is 0 on [b, M].

All functions return exact Fractions.
"""
from __future__ import annotations

from fractions import Fraction as Q

from .pa import q


def g(t, a, b) -> Q:
    t, a, b = q(t), q(a), q(b)
    return max(Q(0), b - t) - max(Q(0), a - t)


def concave_env(t, a, b, M) -> Q:
    """Smallest concave majorant of g on [0, M]: flat b-a on [0, a], then the chord to (M, 0)."""
    t, a, b, M = q(t), q(a), q(b), q(M)
    if t <= a:
        return b - a
    return (b - a) * (M - t) / (M - a)


def convex_env(t, a, b, M) -> Q:
    """Largest convex minorant of g on [0, M]: chord from (0, b-a) to (b, 0), then 0."""
    t, a, b = q(t), q(a), q(b)
    if t >= b:
        return Q(0)
    return (b - a) * (b - t) / b


def wam_bounds(m, W, a, b, M) -> tuple[Q, Q]:
    """Total m and mean W known, support [0, M]: sharp [min, max] of int g dmu (Jensen-type envelopes)."""
    m = q(m)
    return m * convex_env(W, a, b, M), m * concave_env(W, a, b, M)


def refinancing_share_bounds(W, h, M) -> tuple[Q, Q]:
    """Mean maturity W known, support [0, M]: sharp range of the share maturing within h (h < M).

    The share is the mass in [0, h); the supremum (M - W)/(M - h) is approached by mass just below h and at M.
    """
    W, h, M = q(W), q(h), q(M)
    # Two-point extremals: share x at u in [0, h), 1 - x at v in [h, M], with x*u + (1-x)*v = W.
    # Largest x: u -> h from below, v = M  =>  x = (M - W)/(M - h)  (capped at 1).
    # Smallest x: u = 0, v = h  =>  x = 1 - W/h  (floored at 0).
    hi = min(Q(1), (M - W) / (M - h))
    lo = max(Q(0), 1 - W / h)
    return lo, hi


def bucket_bounds(masses: list, edges: list, a, b, M) -> tuple[Q, Q]:
    """Bucket totals on cells [e_j, e_{j+1}) (last cell closed at M): sharp bounds = sum m_j * inf/sup g on the closure."""
    lo = hi = Q(0)
    es = [q(e) for e in edges] + [q(M)]
    for mj, (l, r) in zip(masses, zip(es, es[1:])):
        mj = q(mj)
        # g is nonincreasing, so sup at the left end and inf at the right end of the closure
        hi += mj * g(l, a, b)
        lo += mj * g(r, a, b)
    return lo, hi


def bucket_mean_bounds(masses: list, means: list, edges: list, a, b, M) -> tuple[Q, Q]:
    """Bucket totals and bucket mean maturities: per bucket, convex/concave envelope of g on the cell at the mean."""
    lo = hi = Q(0)
    es = [q(e) for e in edges] + [q(M)]
    for mj, wj, (l, r) in zip(masses, means, zip(es, es[1:])):
        mj, wj = q(mj), q(wj)
        if mj == 0:
            continue
        lo += mj * _env_on(wj, l, r, a, b, convex=True)
        hi += mj * _env_on(wj, l, r, a, b, convex=False)
    return lo, hi


def _env_on(w, l, r, a, b, convex: bool) -> Q:
    """Convex (or concave) envelope of g restricted to [l, r], evaluated at w in [l, r]."""
    pts = sorted({q(l), q(r)} | {x for x in (q(a), q(b)) if q(l) < x < q(r)})
    vals = [(x, g(x, a, b)) for x in pts]
    # envelope of a piecewise-linear function on finitely many breakpoints: hull of its graph vertices
    best = None
    for i in range(len(vals)):
        for j in range(i, len(vals)):
            (x0, y0), (x1, y1) = vals[i], vals[j]
            if not (x0 <= w <= x1):
                continue
            y = y0 if x1 == x0 else y0 + (y1 - y0) * (w - x0) / (x1 - x0)
            if best is None or (convex and y < best) or (not convex and y > best):
                best = y
    return best
