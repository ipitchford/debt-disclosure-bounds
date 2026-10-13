import sys
from fractions import Fraction as Q
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ddb import closed_forms as cf  # noqa: E402
from ddb.lp import Moment, Problem, bounds, coupled, evaluate, solve  # noqa: E402
from ddb.model import SCENARIOS, Discloser, Ledger, kernel, truth, truth_feasible  # noqa: E402
from ddb.pa import PA, indicator, overlap_after, q  # noqa: E402

M = Q(50)
SET = settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def single(atoms, a, b, moments_fn):
    sup = {"conv": M}
    obj = {"conv": overlap_after(a, b, M)}
    led = Ledger(atoms={"conv": atoms}, supports=sup, perimeter="gross")
    D = Discloser(led)
    moms = moments_fn(D)
    return Problem(supports=sup, objective=obj, moments=moms), led


portfolio = st.lists(
    st.tuples(st.fractions(min_value=0, max_value=50, max_denominator=48), st.integers(min_value=1, max_value=1000)),
    min_size=1, max_size=12,
).map(lambda xs: [(q(t), Q(w)) for t, w in xs])
window = st.tuples(st.integers(0, 9), st.integers(1, 6)).map(lambda ab: (Q(ab[0]), Q(ab[0] + ab[1])))


def test_brief_example_portfolios():
    """The A/B example: equal WAM (10y), year-2 cost 0 vs 0.5 per 1pp on 100."""
    sc = SCENARIOS["gilt"]
    for atoms, expect in (([(Q(10), Q(100))], Q(0)), ([(Q(1), Q(50)), (Q(19), Q(50))], Q(1, 2))):
        led = Ledger(atoms={"conv": atoms}, supports={"conv": M}, perimeter="gross")
        assert truth(led, sc, 1, 2) == expect


@SET
@given(portfolio, window)
def test_wam_only_lp_equals_closed_form(atoms, ab):
    a, b = ab
    pr, led = single(atoms, a, b, lambda D: D.amount("tot", {"conv": Q(1)}) + D.mean("wam", {"conv": Q(1)}))
    lo, hi = bounds(pr)
    m = led.total("conv")
    W = sum(t * w for t, w in atoms) / m
    clo, chi = cf.wam_bounds(m, W, a, b, M)
    assert lo.value == clo and hi.value == chi
    t = evaluate(pr.objective, led.atoms, led.supports)
    assert lo.value <= t <= hi.value


@SET
@given(portfolio, window, st.lists(st.integers(1, 49), min_size=1, max_size=5, unique=True))
def test_bucket_totals_lp_equals_closed_form(atoms, ab, cuts):
    a, b = ab
    edges = [Q(0)] + sorted(Q(c) for c in cuts)
    pr, led = single(atoms, a, b, lambda D: sum(
        (D.amount(f"b{i}", {"conv": Q(1)}, l, r) for i, (l, r) in enumerate(zip(edges, edges[1:] + [None]))), []))
    lo, hi = bounds(pr)
    masses = [sum((w for t, w in atoms if l <= t and (r is None or t < r)), Q(0)) for l, r in zip(edges, edges[1:] + [None])]
    clo, chi = cf.bucket_bounds(masses, edges, a, b, M)
    assert lo.value == clo and hi.value == chi


@SET
@given(portfolio, window, st.lists(st.integers(1, 49), min_size=1, max_size=4, unique=True))
def test_bucket_means_lp_equals_closed_form(atoms, ab, cuts):
    a, b = ab
    edges = [Q(0)] + sorted(Q(c) for c in cuts)
    cells = list(zip(edges, edges[1:] + [None]))

    def moms(D):
        out = []
        for i, (l, r) in enumerate(cells):
            out += D.amount(f"b{i}", {"conv": Q(1)}, l, r)
            inb = [w for t, w in atoms if l <= t and (r is None or t < r)]
            if inb:
                out += D.mean(f"m{i}", {"conv": Q(1)}, l, r)
        return out
    pr, led = single(atoms, a, b, moms)
    lo, hi = bounds(pr)
    masses, means = [], []
    for l, r in cells:
        sel = [(t, w) for t, w in atoms if l <= t and (r is None or t < r)]
        mj = sum((w for _, w in sel), Q(0))
        masses.append(mj)
        means.append(sum((t * w for t, w in sel), Q(0)) / mj if mj else Q(0))
    clo, chi = cf.bucket_mean_bounds(masses, means, edges, a, b, M)
    assert lo.value == clo and hi.value == chi


@SET
@given(portfolio, st.integers(1, 10))
def test_refinancing_share_closed_form(atoms, h):
    h = Q(h)
    sup = {"conv": M}
    led = Ledger(atoms={"conv": atoms}, supports=sup, perimeter="gross")
    D = Discloser(led)
    m = led.total("conv")
    pr = Problem(supports=sup, objective={"conv": indicator(0, h).scale(1 / m)},
                 moments=D.amount("tot", {"conv": Q(1)}) + D.mean("wam", {"conv": Q(1)}))
    lo, hi = bounds(pr)
    W = sum(t * w for t, w in atoms) / m
    clo, chi = cf.refinancing_share_bounds(W, h, M)
    assert lo.value == clo and hi.value == chi


@SET
@given(portfolio)
def test_annual_amounts_and_means_identify_every_annual_window(atoms):
    years = [Q(k) for k in range(0, 6)]

    def moms(D):
        out = []
        for l, r in zip(years, years[1:]):
            out += D.amount(f"a{l}", {"conv": Q(1)}, l, r)
            if any(l <= t < r for t, _ in atoms):
                out += D.mean(f"m{l}", {"conv": Q(1)}, l, r)
        return out + D.amount("rest", {"conv": Q(1)}, 5, None)
    for k in range(1, 6):
        pr, led = single(atoms, k - 1, k, moms)
        lo, hi = bounds(pr)
        t = evaluate(pr.objective, led.atoms, led.supports)
        assert lo.value == hi.value == t


@SET
@given(portfolio, window, st.lists(st.fractions(min_value=0, max_value=50, max_denominator=7), min_size=1, max_size=6))
def test_breakpoint_reduction_invariant_to_refinement(atoms, ab, extra):
    """Adding spurious edges (a finer grid) must not change the bounds: the breakpoint LP is exact."""
    a, b = ab
    pr, led = single(atoms, a, b, lambda D: D.amount("tot", {"conv": Q(1)}) + D.mean("wam", {"conv": Q(1)})
                     + D.amount("1y", {"conv": Q(1)}, 0, 1))
    lo, hi = bounds(pr)
    for i, e in enumerate(sorted(set(q(x) for x in extra))):
        if e + Q(1, 1000) <= M:
            pr.moments.append(Moment(f"refine{i}", {"conv": PA.make([(e, e + Q(1, 1000), 0, 0)])}, None, None))
    lo2, hi2 = bounds(pr)
    assert (lo.value, hi.value) == (lo2.value, hi2.value)


@SET
@given(portfolio, window)
def test_coupled_lp_without_extra_equals_width(atoms, ab):
    a, b = ab
    pr, _ = single(atoms, a, b, lambda D: D.amount("tot", {"conv": Q(1)}) + D.mean("wam", {"conv": Q(1)}))
    lo, hi = bounds(pr)
    w = solve(coupled(pr, []), "max").value
    assert w == hi.value - lo.value


@SET
@given(portfolio, window)
def test_coupled_lp_with_identifying_extra_is_zero(atoms, ab):
    """Disclosing the kernel itself (the 'ready reckoner') leaves zero worst-case width."""
    a, b = ab
    pr, _ = single(atoms, a, b, lambda D: D.amount("tot", {"conv": Q(1)}) + D.mean("wam", {"conv": Q(1)}))
    w = solve(coupled(pr, [("rr", pr.objective)]), "max").value
    assert w == 0


def test_identification_requires_span():
    """Kernel not in the span of disclosed moments on the support of the truth => strictly positive width."""
    atoms = [(Q(1, 2), Q(10)), (Q(3, 2), Q(10)), (Q(20), Q(30))]
    pr, led = single(atoms, 0, 1, lambda D: D.amount("tot", {"conv": Q(1)}) + D.amount("1y", {"conv": Q(1)}, 0, 1))
    lo, hi = bounds(pr)
    assert hi.value - lo.value == Q(10)  # the 10 maturing within year 1 could mature at any time in [0,1)


def test_uk_paths_agree_and_cover():
    from ddb.truth_direct import uk_truth
    from ddb.uk import build_ledger, disclosure_sets
    from ddb.model import problem
    for per in ("gross", "consolidated", "consolidated_bank"):
        led = build_ledger(per)
        for sk, sc in SCENARIOS.items():
            for k in range(1, 6):
                tB = truth(led, sc, k - 1, k)
                tA = uk_truth(per, float(sc.dg), float(sc.ds), float(sc.dpi), k - 1, k)
                assert abs(float(tB) - tA) <= 1e-9 * max(1.0, abs(tA))
        for name, (mom, cpl) in disclosure_sets(led).items():
            for sk, sc in SCENARIOS.items():
                for k in (1, 3, 5):
                    lo, hi = bounds(problem(led, sc, k - 1, k, mom, cpl))
                    t = truth(led, sc, k - 1, k)
                    assert lo.value <= t <= hi.value, (per, name, sk, k)
                    assert truth_feasible(led, mom, cpl) == []
                    if name.startswith("D*"):
                        assert lo.value == hi.value == t


@SET
@given(portfolio.map(lambda xs: [(Q(round(t * 1461 / 4)) * Q(4, 1461), w) for t, w in xs]), window)
def test_daily_grid_bounds_attained_and_inside_continuum(atoms, ab):
    """On the daily grid every bound is attained by an explicit grid portfolio (witness checked inside
    solve) and lies inside the continuum interval, from which it differs by at most a day's exposure."""
    a, b = ab
    pr, led = single(atoms, a, b, lambda D: D.amount("tot", {"conv": Q(1)}) + D.mean("wam", {"conv": Q(1)})
                     + D.amount("1y", {"conv": Q(1)}, 0, 1))
    clo, chi = bounds(pr)
    pr.grid = Q(4, 1461)
    glo, ghi = bounds(pr)
    t = evaluate(pr.objective, led.atoms, led.supports)
    assert clo.value <= glo.value <= t <= ghi.value <= chi.value
    m = led.total("conv")
    assert chi.value - ghi.value <= 2 * m * Q(4, 1461) and glo.value - clo.value <= 2 * m * Q(4, 1461)


@SET
@given(portfolio, st.lists(st.integers(-300, 300), min_size=5, max_size=5), st.integers(1, 5))
def test_annual_profile_identifies_any_yearly_shock_path(atoms, path, k):
    """Debt refixing in year j locks the year-j shock d_j. For any such path (constant within years) the
    window-k cost kernel is d_j * overlap_after(t) on year j: affine on every year cell, so the annual
    amounts and mean dates identify it exactly."""
    a, b = Q(k - 1), Q(k)
    cells = []
    for j in range(1, 6):
        lo, hi = Q(j - 1), Q(j)
        dj = Q(path[j - 1], 100)
        for (x0, x1, al, be) in overlap_after(a, b, M).cells:
            s, e = max(lo, x0), min(hi, x1)
            if s < e:
                cells.append((s, e, dj * al, dj * be))
    obj = {"conv": PA.make(cells)}
    led = Ledger(atoms={"conv": atoms}, supports={"conv": M}, perimeter="gross")
    D = Discloser(led)
    moms = []
    for l in range(5):
        moms += D.amount(f"a{l}", {"conv": Q(1)}, l, l + 1)
        if any(l <= t < l + 1 for t, _ in atoms):
            moms += D.mean(f"m{l}", {"conv": Q(1)}, l, l + 1)
    moms += D.amount("rest", {"conv": Q(1)}, 5, None)
    lo_, hi_ = bounds(Problem(supports={"conv": M}, objective=obj, moments=moms))
    assert lo_.value == hi_.value == evaluate(obj, led.atoms, led.supports)


@SET
@given(portfolio, window, st.sampled_from([Q(1, 10), Q(1, 2), Q(1)]))
def test_rounded_average_maturity_interval(atoms, ab, prec):
    """A published average maturity rounded to `prec` becomes two inequality rows; the envelopes are
    nonincreasing in W, so inf uses the top of the rounding interval and sup the bottom."""
    a, b = ab
    sup = {"conv": M}
    led = Ledger(atoms={"conv": atoms}, supports=sup, perimeter="gross")
    D = Discloser(led, {"years": prec})
    pr = Problem(supports=sup, objective={"conv": overlap_after(a, b, M)},
                 moments=D.amount("tot", {"conv": Q(1)}) + D.mean("wam", {"conv": Q(1)}))
    lo, hi = bounds(pr)
    m = led.total("conv")
    W = sum(t * w for t, w in atoms) / m
    r = round(W / prec) * prec
    wlo, whi = max(Q(0), r - prec / 2), min(M, r + prec / 2)
    assert lo.value == m * cf.convex_env(whi, a, b, M)
    assert hi.value == m * cf.concave_env(wlo, a, b, M)


def test_coupling_requires_equal_supports():
    from ddb.lp import Coupling, LPError
    pr = Problem(supports={"a": Q(1), "b": Q(2)}, objective={"a": PA.make([(0, 1, 1, 0)])},
                 moments=[Moment("tot", {"a": PA.make([(0, 1, 1, 0)])}, Q(1), Q(1))],
                 couplings=[Coupling("a<=b", {"a": Q(1), "b": Q(-1)})], grid=Q(1))
    with pytest.raises(LPError):
        bounds(pr)
