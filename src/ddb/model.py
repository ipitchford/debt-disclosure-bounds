"""Refixing ledger, scenario kernels and disclosure statistics.

Components (each a nonnegative measure over residual maturity t, in years from the shock date):
  conv    conventional (fixed-coupon) bonds, face value, all holders
  apf_face  face value of conventional bonds held by the central bank's QE facility (subset of conv)
  apf_ipp   initial purchase proceeds; hypothetical funding in a synthetic scenario
  ilg3, ilg8  index-linked bonds, inflation-uplifted principal, 3- and 8-month indexation lags
  ilg3n, ilg8n  the same bonds at nominal (un-uplifted) value
  bill    Treasury bills, face value
  frn     floating-rate notes (US), face value; coupon resets weekly, so they refix at t = 0

Estimand.  First-order incremental accrued interest in the window [a, b) (years after the shock date)
from permanent shocks dg (yields on newly issued bonds), ds (short rates: bills, reserves, FRN index)
and dpi (inflation), holding amounts at their valuation-date values and refinancing each maturing
amount like-for-like on the same rate leg. In the consolidated perimeter the face of QE-held bonds is
removed from the privately held stock and the hypothetical IPP funding pays the short rate until the
bond matures, after which the IPP is refinanced on the bond leg.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as Q

from .lp import Coupling, Moment, Problem, evaluate
from .pa import PA, const, indicator, overlap_after, overlap_before, q

ILG_LAG = {"ilg3": Q(3, 12), "ilg8": Q(8, 12)}
NOMINAL_OF = {"ilg3": "ilg3n", "ilg8": "ilg8n"}


@dataclass(frozen=True)
class Scenario:
    name: str
    dg: Q
    ds: Q
    dpi: Q


PP = Q(1, 100)
SCENARIOS = {
    "all": Scenario("all rates +1pp", PP, PP, Q(0)),
    "gilt": Scenario("bond yields +1pp", PP, Q(0), Q(0)),
    "short": Scenario("short rates +1pp", Q(0), PP, Q(0)),
    "infl": Scenario("inflation +1pp", Q(0), Q(0), PP),
}


@dataclass
class Ledger:
    """Truth: atoms per component, and support maxima."""
    atoms: dict[str, list[tuple[Q, Q]]]
    supports: dict[str, Q]
    perimeter: str  # "gross" or "consolidated"

    def total(self, comp: str) -> Q:
        return sum((w for _, w in self.atoms.get(comp, [])), Q(0))


# Rate behaviour of each component: fixed coupon (refix at maturity on the bond leg), index-linked
# (bond leg at maturity, plus inflation accrual after the indexation lag), bill (short leg from
# maturity), frn (short leg throughout).
KIND = {
    "conv": ("fixed", None), "note": ("fixed", None), "bond": ("fixed", None),
    "ilg3": ("ilg", Q(3, 12)), "ilg8": ("ilg", Q(8, 12)), "tips": ("ilg", Q(3, 12)),
    "bill": ("bill", None), "frn": ("frn", None),
    "notes": ("notes", None),
}


def kernel(sc: Scenario, a, b, supports: dict[str, Q], perimeter: str) -> dict[str, PA]:
    a, b = q(a), q(b)
    k: dict[str, PA] = {}
    for c, smax in supports.items():
        if c not in KIND:
            continue
        kind, lag = KIND[c]
        if kind == "fixed":
            k[c] = overlap_after(a, b, smax).scale(sc.dg)
        elif kind == "ilg":
            infl = max(Q(0), b - max(a, lag)) if b > lag else Q(0)
            k[c] = overlap_after(a, b, smax).scale(sc.dg) + const(sc.dpi * infl, 0, smax)
        elif kind == "bill":
            k[c] = overlap_after(a, b, smax).scale(sc.ds)
        elif kind == "frn":
            k[c] = const(sc.ds * (b - a), 0, smax)
        elif kind == "notes":
            # conditional banknote allocation, not validated whole-Bank consolidation
            k[c] = const(-sc.ds * (b - a), 0, smax)
    if perimeter.startswith("consolidated"):
        M = supports
        k["apf_face"] = overlap_after(a, b, M["apf_face"]).scale(-sc.dg)
        k["apf_ipp"] = overlap_before(a, b, M["apf_ipp"]).scale(sc.ds) + overlap_after(a, b, M["apf_ipp"]).scale(sc.dg)
    return {c: f for c, f in k.items() if f.cells}


def truth(led: Ledger, sc: Scenario, a, b) -> Q:
    return evaluate(kernel(sc, a, b, led.supports, led.perimeter), led.atoms, led.supports)


# ----------------------------------------------------------------------------------------------
# Disclosure statistics.  A "group" is a weighted set of components measured in one unit.
# ----------------------------------------------------------------------------------------------

Group = dict[str, Q]


def g_(**w) -> Group:
    return {k: q(v) for k, v in w.items()}


def _terms(group: Group, f_of_comp) -> dict[str, PA]:
    out = {}
    for c, w in group.items():
        f = f_of_comp(c)
        if f is not None and f.cells:
            out[c] = f.scale(w)
    return out


class Discloser:
    """Builds moment constraints whose values are computed exactly from the true ledger.

    `refix` maps a component to the point at which its rate refixes for refixing-based statistics
    (ATR, share refixing within h): None means at maturity t, a number means a constant time (e.g. 0
    for funding reserves and floating-rate notes).
    """

    def __init__(self, led: Ledger, precision: dict | None = None):
        self.led = led
        self.S = led.supports
        self.prec = precision or {}

    def _round(self, kind: str, v: Q) -> tuple[Q, Q]:
        p = self.prec.get(kind)
        if p is None:
            return v, v
        p = q(p)
        r = round(v / p) * p
        return r - p / 2, r + p / 2

    def _value(self, terms):
        return evaluate(terms, self.led.atoms, self.S)

    def amount(self, name, group: Group, a=0, b=None, kind="amount") -> list[Moment]:
        def f(c):
            hi = self.S[c] if b is None else min(q(b), self.S[c])
            lo = q(a)
            if lo >= self.S[c]:
                return None
            if b is None or q(b) >= self.S[c]:
                return PA.make([(lo, self.S[c], 1, 0)])
            return indicator(lo, hi)
        terms = _terms(group, f)
        v = self._value(terms)
        lo, hi = self._round(kind, v)
        return [Moment(name, terms, lo, hi)]

    def mean(self, name, group: Group, a=0, b=None, kind="years", refix: dict | None = None) -> list[Moment]:
        """Amount-weighted mean (maturity or refix time) of the group within [a, b)."""
        refix = refix or {}

        def mk(shift: Q):
            def f(c):
                smax = self.S[c]
                lo = q(a)
                hi = smax if b is None else min(q(b), smax)
                if c in refix and refix[c] is not None:
                    r = q(refix[c])
                    inside = (lo <= r < hi) or (r == hi == smax)
                    return const(r - shift, 0, smax) if inside else None
                if lo >= smax:
                    return None
                return PA.make([(lo, hi, -shift, 1)])
            return f
        num = self._value(_terms(group, mk(Q(0))))
        den = self._value(_terms(group, mk_amount(self.S, a, b, refix)))
        if den == 0:
            raise ValueError(f"empty group for mean {name}")
        mval = num / den
        lo, hi = self._round(kind, mval)
        out = []
        if lo == hi:
            out.append(Moment(name, _terms(group, mk(lo)), Q(0), Q(0)))
        else:
            out.append(Moment(name + "[lo]", _terms(group, mk(lo)), Q(0), None))
            out.append(Moment(name + "[hi]", _terms(group, mk(hi)), None, Q(0)))
        return out

    def share(self, name, num: Group, den: Group, a=0, b=None, kind="share", refix: dict | None = None) -> list[Moment]:
        """Share of `den` total represented by `num` within [a, b) (maturity, or refix time)."""
        refix = refix or {}
        fnum = mk_amount(self.S, a, b, refix)
        fden = mk_amount(self.S, 0, None, {})
        vnum = self._value(_terms(num, fnum))
        vden = self._value(_terms(den, fden))
        s = vnum / vden
        lo, hi = self._round(kind, s)

        def combo(sv):
            t = _terms(num, fnum)
            for c, f in _terms(den, fden).items():
                g = f.scale(-sv)
                t[c] = t[c] + g if c in t else g
            return t
        if lo == hi:
            return [Moment(name, combo(lo), Q(0), Q(0))]
        return [Moment(name + "[lo]", combo(lo), Q(0), None), Moment(name + "[hi]", combo(hi), None, Q(0))]


def mk_amount(S, a, b, refix):
    def f(c):
        smax = S[c]
        lo = q(a)
        hi = smax if b is None else min(q(b), smax)
        if c in refix and refix[c] is not None:
            r = q(refix[c])
            inside = (lo <= r < hi) or (r == hi == smax)
            return const(1, 0, smax) if inside else None
        if lo >= smax:
            return None
        if b is None or q(b) >= smax:
            return PA.make([(lo, smax, 1, 0)])
        return indicator(lo, hi)
    return f


def apf_couplings(r_lo: Q, r_hi: Q) -> list[Coupling]:
    """QE holdings are a subset of conventional face; IPP per unit face lies in [r_lo, r_hi]."""
    return [
        Coupling("apf<=conv", {"apf_face": Q(1), "conv": Q(-1)}),
        Coupling("ipp<=rhi*face", {"apf_ipp": Q(1), "apf_face": -q(r_hi)}),
        Coupling("ipp>=rlo*face", {"apf_ipp": Q(-1), "apf_face": q(r_lo)}),
    ]


def ilg_couplings(u_lo: Q, u_hi: Q) -> list[Coupling]:
    out = []
    for c, n in NOMINAL_OF.items():
        out.append(Coupling(f"{c}<=uhi*nom", {c: Q(1), n: -q(u_hi)}))
        out.append(Coupling(f"{c}>=ulo*nom", {c: Q(-1), n: q(u_lo)}))
    return out


DAY = Q(4, 1461)   # one calendar day in years (ACT/365.25); maturities fall on calendar days


def problem(led: Ledger, sc: Scenario, a, b, moments: list[Moment], couplings: list[Coupling], grid=DAY) -> Problem:
    obj = kernel(sc, a, b, led.supports, led.perimeter)
    return Problem(supports=led.supports, objective=obj, moments=moments, couplings=couplings, grid=grid)


def first_moment(D: "Discloser", name, group: Group, a=0, b=None) -> list[Moment]:
    """int t * 1[a,b)(t) dmu over the group (the numerator of a within-bucket mean)."""
    def f(c):
        smax = D.S[c]
        lo = q(a)
        hi = smax if b is None else min(q(b), smax)
        if lo >= smax:
            return None
        return PA.make([(lo, hi, 0, 1)])
    terms = _terms(group, f)
    v = D._value(terms)
    lo, hi = D._round("first_moment", v)
    return [Moment(name, terms, lo, hi)]


def truth_feasible(led: Ledger, moments: list[Moment], couplings: list[Coupling]) -> list[str]:
    """Exact check that the actual ledger satisfies every disclosed statistic and coupling.

    Returns the names of violated constraints (empty if the truth is feasible). Coverage is only
    claimed for feasible truths; an infeasible truth means the disclosure or prior is mis-specified.
    """
    bad = []
    for m in moments:
        v = evaluate(m.terms, led.atoms, led.supports)
        if (m.lo is not None and v < m.lo) or (m.hi is not None and v > m.hi):
            bad.append(m.name)
    for cp in couplings:
        at: dict = {}
        for c, w in cp.weights.items():
            for t, x in led.atoms.get(c, []):
                at[t] = at.get(t, Q(0)) + q(w) * x
        if any(v > 0 for v in at.values()):
            bad.append(cp.name)
    return bad
