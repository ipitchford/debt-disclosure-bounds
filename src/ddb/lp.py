"""Exact bounds on a linear functional of nonnegative measures subject to linear moment constraints.

Problem.  Components c = 1..C carry nonnegative measures mu_c on [0, smax_c]. Given

    objective   J(mu)  = sum_c  int g_c(t) dmu_c(t)
    moments     lo_i  <= sum_c  int f_{i,c}(t) dmu_c(t) <= hi_i
    couplings   sum_c  w_{j,c} mu_c(dt) <= 0  pointwise (same t for all components involved)

with every g_c, f_{i,c} piecewise affine (pa.PA), compute inf J and sup J.

Breakpoint reduction.  Let E be the union of all cell edges (plus 0 and each smax). On every cell
between consecutive edges all functions are affine, so an atom at an interior point can be split into
two atoms at the cell's end points with weights that preserve every affine integrand; applying the same
split to all components at that point preserves the pointwise couplings. Hence the LP over measures
supported on the one-sided edge points {(e,'L'), (e,'R')} has the same inf and sup as the problem over
all measures (attained or approached as a one-sided limit). The LP below is therefore exact.

Certificates.  HiGHS solves in floating point; the optimal basis it reports is then re-solved in exact
rational arithmetic (python-flint), and primal feasibility, dual feasibility and equality of primal and
dual objectives are checked exactly. A bound is reported only if this check passes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction as Q

from .pa import PA, q

INF = float("inf")


@dataclass
class Moment:
    name: str
    terms: dict[str, PA]
    lo: Q | None
    hi: Q | None


@dataclass
class Coupling:
    name: str
    weights: dict[str, Q]   # sum_c w_c * x_c(point) <= 0 at each shared point


@dataclass
class Problem:
    supports: dict[str, Q]                 # component -> smax
    objective: dict[str, PA]
    moments: list[Moment]
    couplings: list[Coupling] = field(default_factory=list)
    grid: Q | None = None                  # None: continuum (one-sided edge points); else grid step

    def components(self) -> list[str]:
        used = set(self.objective)
        for m in self.moments:
            used |= set(m.terms)
        for c in self.couplings:
            used |= set(c.weights)
        return sorted(used)

    def edges(self) -> list[Q]:
        es: set[Q] = {Q(0)}
        for f in self.objective.values():
            es |= f.edges()
        for m in self.moments:
            for f in m.terms.values():
                es |= f.edges()
        es |= set(self.supports.values())
        return sorted(es)

    def points(self, comp: str) -> list[tuple[Q, str]]:
        smax = self.supports[comp]
        es = [e for e in self.edges() if e <= smax]
        pts = []
        if self.grid is None:
            for e in es:
                if e > 0:
                    pts.append((e, "L"))
                if e < smax:
                    pts.append((e, "R"))
            return pts
        h = self.grid
        top = (smax // h) * h                      # last grid point within the support
        cand = {Q(0), top}
        for e in es:
            up = -((-e) // h) * h                  # smallest grid point >= e
            if up <= top:
                cand.add(up)
            if e > 0:
                cand.add(up - h if up >= e else up)  # largest grid point < e
        return [(t, "L" if t == smax else "R") for t in sorted(c for c in cand if 0 <= c <= top)]


@dataclass
class Bound:
    value: Q                                  # certified optimal value (exact)
    measure: dict[str, list[tuple[Q, str, Q]]]  # extremal measure: comp -> [(t, side, mass)]
    certified: bool
    dual: list[tuple[int, Q]] = field(default_factory=list)  # nonzero row multipliers (row index, y)
    sense: str = "min"


class LPError(RuntimeError):
    pass


def _build(prob: Problem):
    comps = prob.components()
    cols = []  # (comp, point)
    for c in comps:
        for p in prob.points(c):
            cols.append((c, p))
    colidx = {cp: j for j, cp in enumerate(cols)}
    n = len(cols)
    obj = [Q(0)] * n
    for j, (c, (t, s)) in enumerate(cols):
        if c in prob.objective:
            obj[j] = prob.objective[c].at(t, s)
    rows, rlo, rhi, rnames = [], [], [], []
    for m in prob.moments:
        coef = {}
        for c, f in m.terms.items():
            for p in prob.points(c):
                v = f.at(*p)
                if v != 0:
                    coef[colidx[(c, p)]] = v
        rows.append(coef)
        rlo.append(m.lo)
        rhi.append(m.hi)
        rnames.append(m.name)
    for cp in prob.couplings:
        comps_c = list(cp.weights)
        if len({prob.supports[c] for c in comps_c}) != 1:
            raise LPError(f"coupling {cp.name} joins components with different supports")
        common = set(prob.points(comps_c[0]))
        for p in sorted(common):
            coef = {colidx[(c, p)]: q(w) for c, w in cp.weights.items() if q(w) != 0}
            rows.append(coef)
            rlo.append(None)
            rhi.append(Q(0))
            rnames.append(f"{cp.name}@{float(p[0]):.4f}{p[1]}")
    return cols, obj, rows, rlo, rhi, rnames


def _solve_float(obj, rows, rlo, rhi, n, sense, tol=1e-9):
    import highspy
    import numpy as np
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("primal_feasibility_tolerance", tol)
    h.setOptionValue("dual_feasibility_tolerance", tol)
    lp = highspy.HighsLp()
    lp.num_col_ = n
    lp.num_row_ = len(rows)
    sgn = 1.0 if sense == "min" else -1.0
    lp.col_cost_ = np.array([sgn * float(c) for c in obj])
    lp.col_lower_ = np.zeros(n)
    lp.col_upper_ = np.full(n, INF)
    lp.row_lower_ = np.array([-INF if v is None else float(v) for v in rlo])
    lp.row_upper_ = np.array([INF if v is None else float(v) for v in rhi])
    # column-wise sparse matrix
    starts, index, value = [0], [], []
    colrows = [[] for _ in range(n)]
    for i, coef in enumerate(rows):
        for j, v in coef.items():
            colrows[j].append((i, float(v)))
    for j in range(n):
        for i, v in sorted(colrows[j]):
            index.append(i)
            value.append(v)
        starts.append(len(index))
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_ = np.array(starts, dtype=np.int32)
    lp.a_matrix_.index_ = np.array(index, dtype=np.int32)
    lp.a_matrix_.value_ = np.array(value)
    h.passModel(lp)
    h.run()
    st = h.getModelStatus()
    if st != highspy.HighsModelStatus.kOptimal:
        raise LPError(f"HiGHS status {h.modelStatusToString(st)}")
    basis = h.getBasis()
    col_status = [str(s).split(".")[-1] for s in basis.col_status]
    row_status = [str(s).split(".")[-1] for s in basis.row_status]
    return col_status, row_status


def _certify(obj, rows, rlo, rhi, n, sense, col_status, row_status):
    """Exact re-solve of the reported basis. Variables z = (x_1..x_n, r_1..r_m) with A x - r = 0."""
    from flint import fmpq, fmpq_mat
    m = len(rows)
    sgn = Q(1) if sense == "min" else Q(-1)
    cost = [sgn * c for c in obj] + [Q(0)] * m
    lower = [Q(0)] * n + [v for v in rlo]
    upper = [None] * n + [v for v in rhi]
    status = col_status + row_status
    basic = [k for k, s in enumerate(status) if s == "kBasic"]
    if len(basic) != m:
        raise LPError(f"basis size {len(basic)} != rows {m}")
    # value of nonbasic variables
    val: dict[int, Q] = {}
    for k, s in enumerate(status):
        if s == "kBasic":
            continue
        if s == "kLower":
            if lower[k] is None:
                raise LPError("nonbasic at missing lower bound")
            val[k] = lower[k]
        elif s == "kUpper":
            if upper[k] is None:
                raise LPError("nonbasic at missing upper bound")
            val[k] = upper[k]
        elif s == "kZero":
            val[k] = Q(0)
        else:
            raise LPError(f"unexpected status {s}")

    def colvec(k):  # column of [A, -I]
        if k < n:
            return {i: coef[k] for i, coef in enumerate(rows) if k in coef}
        return {k - n: Q(-1)}

    B = fmpq_mat(m, m)
    for jj, k in enumerate(basic):
        for i, v in colvec(k).items():
            B[i, jj] = fmpq(v.numerator, v.denominator)
    rhs = fmpq_mat(m, 1)
    for k, v in val.items():
        if v == 0:
            continue
        for i, a in colvec(k).items():
            prod = a * v
            rhs[i, 0] -= fmpq(prod.numerator, prod.denominator)
    try:
        zb = B.solve(rhs)
    except ZeroDivisionError as e:
        raise LPError("singular basis") from e
    z = dict(val)
    for jj, k in enumerate(basic):
        e = zb[jj, 0]
        z[k] = Q(int(e.p), int(e.q))
    for k in range(n + m):
        if lower[k] is not None and z[k] < lower[k]:
            raise LPError(f"primal infeasible var {k}: {float(z[k])} < {float(lower[k])}")
        if upper[k] is not None and z[k] > upper[k]:
            raise LPError(f"primal infeasible var {k}: {float(z[k])} > {float(upper[k])}")
    # duals: B^T y = c_B
    cb = fmpq_mat(m, 1)
    for jj, k in enumerate(basic):
        cb[jj, 0] = fmpq(cost[k].numerator, cost[k].denominator)
    yv = B.transpose().solve(cb)
    y = [Q(int(yv[i, 0].p), int(yv[i, 0].q)) for i in range(m)]
    for k in range(n + m):
        if status[k] == "kBasic":
            continue
        d = cost[k] - sum((a * y[i] for i, a in colvec(k).items()), Q(0))
        st = status[k]
        if st == "kLower" and d < 0 and not (upper[k] is not None and lower[k] == upper[k]):
            raise LPError(f"dual infeasible at lower var {k}: {float(d)}")
        if st == "kUpper" and d > 0 and not (lower[k] is not None and lower[k] == upper[k]):
            raise LPError(f"dual infeasible at upper var {k}: {float(d)}")
        if st == "kZero" and d != 0:
            raise LPError(f"nonzero reduced cost on free nonbasic var {k}: {float(d)}")
    primal = sum((cost[k] * z[k] for k in range(n + m)), Q(0))
    # dual objective: sum over nonbasic bound values times reduced cost (with zero rhs on A x - r = 0)
    dual = Q(0)
    for k in range(n + m):
        if status[k] == "kBasic":
            continue
        d = cost[k] - sum((a * y[i] for i, a in colvec(k).items()), Q(0))
        dual += d * z[k]
    if primal != dual:
        raise LPError("primal and dual objectives differ")
    return sgn * primal, z, y


def solve(prob: Problem, sense: str) -> Bound:
    if sense not in ('min', 'max'):
        raise LPError('Unknown certificate sense')
    cols, obj, rows, rlo, rhi, _ = _build(prob)
    n = len(cols)
    last = None
    for tol in (1e-9, 1e-7, 1e-6):
        try:
            col_status, row_status = _solve_float(obj, rows, rlo, rhi, n, sense, tol)
            value, z, y = _certify(obj, rows, rlo, rhi, n, sense, col_status, row_status)
            break
        except LPError as e:  # float trouble: retry looser; only an exactly certified basis is accepted
            last = e
    else:
        raise LPError(f"no certified optimum: {last}")
    meas: dict[str, list] = {}
    for j, (c, (t, s)) in enumerate(cols):
        if z[j] != 0:
            meas.setdefault(c, []).append((t, s, z[j]))
    sgn = Q(1) if sense == "min" else Q(-1)
    dual = [(i, sgn * yi) for i, yi in enumerate(y) if yi != 0]
    b = Bound(value=value, measure=meas, certified=True, dual=dual, sense=sense)
    witness_check(prob, b)
    check_certificate(prob, b.sense, b.value, b.measure, b.dual)
    return b


def bounds(prob: Problem) -> tuple[Bound, Bound]:
    return solve(prob, "min"), solve(prob, "max")


def evaluate(f_terms: dict[str, PA], atoms: dict[str, list[tuple[Q, Q]]], supports: dict[str, Q]) -> Q:
    """sum_c int f_c d(atoms_c) for an actual (atomic) measure; edge convention as in pa.PA."""
    tot = Q(0)
    for c, f in f_terms.items():
        smax = supports[c]
        for t, w in atoms.get(c, []):
            side = "L" if t == smax else "R"
            tot += w * f.at(t, side)
    return tot


def coupled(prob: Problem, extra_terms: list[tuple[str, dict[str, PA]]]) -> Problem:
    """Two copies of `prob` whose `extra_terms` moments take equal (but unknown) values.

    max  J(mu1) - J(mu2)  over the coupled problem is the worst-case width of the identified set for J
    after the extra statistics are disclosed, taken over every value they could take given what `prob`
    already discloses (the ex-ante, guaranteed informativeness of the extra disclosure). With no extra
    terms it is the width of the identified set under `prob` itself.
    """
    def ren(d, tag):
        return {f"{c}@{tag}": f for c, f in d.items()}

    sup = {}
    for tag in ("1", "2"):
        sup.update({f"{c}@{tag}": s for c, s in prob.supports.items()})
    obj = ren(prob.objective, "1")
    obj.update({c: f.scale(-1) for c, f in ren(prob.objective, "2").items()})
    moms = []
    for tag in ("1", "2"):
        for m in prob.moments:
            moms.append(Moment(f"{m.name}@{tag}", ren(m.terms, tag), m.lo, m.hi))
    for name, terms in extra_terms:
        t = ren(terms, "1")
        for c, f in ren(terms, "2").items():
            t[c] = f.scale(-1)
        moms.append(Moment(f"couple {name}", t, Q(0), Q(0)))
    cpls = []
    for tag in ("1", "2"):
        for cp in prob.couplings:
            cpls.append(Coupling(f"{cp.name}@{tag}", {f"{c}@{tag}": w for c, w in cp.weights.items()}))
    return Problem(supports=sup, objective=obj, moments=moms, couplings=cpls, grid=prob.grid)


def witness_check(prob: Problem, b: "Bound") -> None:
    """Primal witness: the extremal measure satisfies every constraint exactly and attains the bound."""
    atoms: dict[str, list] = {}
    for c, lst in b.measure.items():
        for t, side, w in lst:
            atoms.setdefault(c, []).append((t, side, w))

    def val(terms):
        tot = Q(0)
        for c, f in terms.items():
            for t, side, w in atoms.get(c, []):
                tot += w * f.at(t, side)
        return tot
    for m in prob.moments:
        v = val(m.terms)
        if (m.lo is not None and v < m.lo) or (m.hi is not None and v > m.hi):
            raise LPError(f"witness violates {m.name}")
    for cp in prob.couplings:
        pts: dict = {}
        for c, w in cp.weights.items():
            for t, side, x in atoms.get(c, []):
                pts[(t, side)] = pts.get((t, side), Q(0)) + q(w) * x
        if any(v > 0 for v in pts.values()):
            raise LPError(f"witness violates coupling {cp.name}")
    if any(w < 0 for lst in atoms.values() for _, _, w in lst):
        raise LPError("negative witness mass")
    if val(prob.objective) != b.value:
        raise LPError("witness objective differs from certified bound")


def check_certificate(prob: Problem, sense: str, value: Q, measure: dict, dual: list) -> None:
    """Independent exact check of an optimality certificate; uses neither HiGHS nor the basis solve.

    Primal: the measure is nonnegative, satisfies every row and attains `value`.
    Dual (multipliers y on rows, in the problem's own sense): for a minimum, A^T y <= c on every
    column, y_i > 0 only on rows with a finite lower bound and y_i < 0 only on rows with a finite
    upper bound; then sum_i y_i * (lo_i if y_i > 0 else hi_i) <= c^T x for every feasible x, and
    equality with `value` proves optimality. For a maximum the inequalities are reversed.
    """
    if sense not in ('min', 'max'):
        raise LPError('Unknown certificate sense')
    cols, obj, rows, rlo, rhi, _ = _build(prob)
    idx = {cp: j for j, cp in enumerate(cols)}
    x = [Q(0)] * len(cols)
    for c, lst in measure.items():
        for t, side, w in lst:
            if w < 0:
                raise LPError("negative primal mass")
            x[idx[(c, (t, side))]] += w
    if sum((c * xj for c, xj in zip(obj, x)), Q(0)) != value:
        raise LPError("primal objective differs from value")
    for i, coef in enumerate(rows):
        act = sum((a * x[j] for j, a in coef.items()), Q(0))
        if (rlo[i] is not None and act < rlo[i]) or (rhi[i] is not None and act > rhi[i]):
            raise LPError(f"primal row {i} violated")
    y = dict(dual)
    if len(y) != len(dual) or any(not isinstance(i, int) or i < 0 or i >= len(rows) for i in y):
        raise LPError('Invalid or duplicate dual row index')
    sgn = Q(1) if sense == "min" else Q(-1)
    aty = [Q(0)] * len(cols)
    for i, yi in y.items():
        for j, a in rows[i].items():
            aty[j] += a * yi
    for j in range(len(cols)):
        if sgn * aty[j] > sgn * obj[j]:
            raise LPError(f"dual infeasible on column {j}")
    dv = Q(0)
    for i, yi in y.items():
        pos = (sgn * yi) > 0
        bound = rlo[i] if pos else rhi[i]
        if bound is None:
            raise LPError(f"dual multiplier on row {i} has the wrong sign for its bounds")
        dv += yi * bound
    if dv != value:
        raise LPError("dual objective differs from value")
