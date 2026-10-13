"""Every linear programme in the paper is built from a JSON-serialisable specification.

The experiment drivers and the standalone certificate verifier both call `build(spec)`, so a stored
certificate can be checked against an independently rebuilt programme.

spec keys:
  country      "uk" | "us"
  perimeter    "gross" | "consolidated" | "consolidated_bank" (UK); "gross" (US)
  set          disclosure-set name
  scenario     key of model.SCENARIOS
  window       key of WINDOWS
  kernel       "first" (default) | "iai" (with interest on the extra interest at 4.5%)
  variant      robustness variant key (see VARIANTS), default "baseline"
  candidate    optional added statistic (value-of-disclosure)
  mode         "bound" | "coupled" (worst-case width with `candidate` coupled across two copies)
"""
from __future__ import annotations

import copy
import functools
from fractions import Fraction as Q

from . import uk, us
from .lp import Problem, coupled
from .model import SCENARIOS, Discloser, Ledger, first_moment, kernel, mk_amount, _terms
from .lp import Moment, evaluate
from .pa import q

WINDOWS = {"y1": (0, 1), "y2": (1, 2), "y3": (2, 3), "y4": (3, 4), "y5": (4, 5), "cum5": (0, 5)}
DAY = Q(4, 1461)

VARIANTS = {
    "baseline": "Baseline (exact statistics)",
    "round_fine": "Rounded: £0.1bn, 0.1 years, 0.1pp",
    "round_coarse": "Rounded: £1bn, 0.5 years, 1pp",
    "M47": "Maximum maturity cap 47.04 years",
    "M60": "Maximum maturity cap 60 years",
    "M100": "Maximum maturity cap 100 years",
    "apf_obs": "QE price range [0.749, 2.354]",
    "apf_tight": "QE price range [0.9, 1.6] (excludes three actual holdings)",
    "mm_wam_nominal": "Mismatch: WAM weights IL gilts at nominal",
    "mm_shift": "Mismatch: maturities measured from 30 Sep",
    "mm_gfs_nobills": "Mismatch: GFS buckets exclude T-bills",
    "mm_apf_face": "Mismatch: QE stock at face read as purchase cost",
}
PRECISION = {"round_fine": {"amount": 100, "years": Q(1, 10), "share": Q(1, 1000)},
             "round_coarse": {"amount": 1000, "years": Q(1, 2), "share": Q(1, 100)}}
M_GILT = {"M47": Q(4704, 100), "M60": Q(60), "M100": Q(100)}
APF_R = {"apf_obs": (Q(749, 1000), Q(2354, 1000)), "apf_tight": (Q(9, 10), Q(8, 5))}


@functools.lru_cache(maxsize=None)
def ledger(country: str, perimeter: str, m_gilt: Q | None = None) -> Ledger:
    if country == "us":
        return us.build_ledger()
    return uk.build_ledger(perimeter, m_gilt) if m_gilt is not None else uk.build_ledger(perimeter)


@functools.lru_cache(maxsize=None)
def _sets(country, perimeter, variant):
    if country == "us":
        return us.disclosure_sets(ledger("us", "gross"))
    led = ledger("uk", perimeter, M_GILT.get(variant))
    if variant in PRECISION:
        return uk.disclosure_sets(led, PRECISION[variant])
    if variant in APF_R:
        return uk.disclosure_sets(led, apf_r=APF_R[variant])
    if variant == "mm_wam_nominal":
        alt = copy.deepcopy(led)
        alt.atoms["ilg3"], alt.atoms["ilg8"] = alt.atoms["ilg3n"], alt.atoms["ilg8n"]
        Dalt = Discloser(alt)
        base = uk.disclosure_sets(led)
        return {k: ([x for x in m if x.name != "gilt WAM"] + (Dalt.mean("gilt WAM", uk.GILTS) if any(x.name == "gilt WAM" for x in m) else []), c)
                for k, (m, c) in base.items()}
    if variant == "mm_shift":
        d = Q(13 * 4, 1461)
        sh = Ledger({c: [(min(t + d, led.supports[c]), w) for t, w in lst] for c, lst in led.atoms.items()},
                    led.supports, led.perimeter)
        return uk.disclosure_sets(sh)
    if variant == "mm_gfs_nobills":
        nob = copy.deepcopy(led)
        nob.atoms["bill"] = []
        base = uk.disclosure_sets(led)
        alt = uk.disclosure_sets(nob)
        m_alt, _ = alt["D2 GFS residual maturity"]
        m_base, c = base["D2 GFS residual maturity"]
        keep = [x for x in m_base if x.name.startswith("APF") or x.name.startswith("banknotes")]
        return {"D2 GFS residual maturity": ([x for x in m_alt if not (x.name.startswith("APF") or x.name.startswith("banknotes"))] + keep, c)}
    if variant == "mm_apf_face":
        base = uk.disclosure_sets(led)
        face = led.total("apf_face")
        out = {}
        for k, (m, c) in base.items():
            if not any(x.name == "APF IPP total" for x in m):
                continue
            mm = [x for x in m if x.name not in ("APF IPP total", "APF face total")]
            ipp = next(x for x in m if x.name == "APF IPP total")
            mm.append(Moment("APF IPP total (actually face)", ipp.terms, face, face))
            out[k] = (mm, c)
        return out
    return uk.disclosure_sets(led)


@functools.lru_cache(maxsize=None)
def candidates(country: str, perimeter: str) -> dict[str, list]:
    led = ledger(country, perimeter)
    D = Discloser(led)
    c: dict[str, list] = {}
    if country == "us":
        ALL = us.ALL
        c["K1 share maturing <1y"] = D.amount("all[0,1)", ALL, 0, 1)
        c["K2 annual maturity amounts y1-5"] = sum((D.amount(f"all[{a},{a+1})", ALL, a, a + 1) for a in range(5)), [])
        c["K4 annual amounts + mean dates y1-5"] = sum((D.amount(f"all[{a},{a+1})", ALL, a, a + 1)
                                                        + first_moment(D, f"t*all[{a},{a+1})", ALL, a, a + 1) for a in range(5)), [])
        c["K8 FRN total"] = D.amount("frn total", {"frn": Q(1)})
        return c
    cons = perimeter.startswith("consolidated")
    ALL = uk.ALL
    c["K1 share maturing <1y"] = D.amount("all[0,1)", ALL, 0, 1)
    k9 = D.amount("all[0,1)", ALL, 0, 1) + first_moment(D, "t*all[0,1)", ALL, 0, 1)
    if cons:
        k9 += D.amount("APF face[0,1)", uk.APF_FACE, 0, 1) + first_moment(D, "t*APF face[0,1)", uk.APF_FACE, 0, 1)
    c["K9 mean maturity of the <1y bucket" + (" (+ APF part)" if cons else "")] = k9
    # The same statistic at publication precision (amount to GBP 0.1bn, mean rounded): realised widths only.
    for lab, p in (("0.1 years", Q(1, 10)), ("0.01 years", Q(1, 100)), ("one day", DAY)):
        Dp = Discloser(led, {"amount": 100, "years": p})
        r9 = Dp.amount("all[0,1)", ALL, 0, 1) + Dp.mean("mean all[0,1)", ALL, 0, 1)
        if cons:
            r9 += Dp.amount("APF face[0,1)", uk.APF_FACE, 0, 1) + Dp.mean("mean APF face[0,1)", uk.APF_FACE, 0, 1)
        c[f"R9 mean of <1y bucket rounded to {lab}"] = r9
    c["K2 annual maturity amounts y1-5"] = sum((D.amount(f"all[{a},{a+1})", ALL, a, a + 1) for a in range(5)), [])
    k3 = []
    for grp, nm in ((uk.CONV, "conv"), (uk.ILG, "IL")):
        for a, b in zip(uk.DMO_EDGES, uk.DMO_EDGES[1:] + [None]):
            k3 += D.amount(f"{nm}[{a},{b})", grp, a, b) + first_moment(D, f"t*{nm}[{a},{b})", grp, a, b)
    c["K3 mean maturity within DMO brackets"] = k3
    c["K4 annual amounts + mean dates y1-5"] = sum((D.amount(f"all[{a},{a+1})", ALL, a, a + 1)
                                                    + first_moment(D, f"t*all[{a},{a+1})", ALL, a, a + 1) for a in range(5)), [])
    if cons:
        k5 = []
        for grp, nm in ((uk.APF_IPP, "APF IPP"), (uk.APF_FACE, "APF face")):
            for a, b in zip(uk.DMO_EDGES, uk.DMO_EDGES[1:] + [None]):
                k5 += D.amount(f"{nm}[{a},{b})", grp, a, b)
        c["K5 APF holdings by DMO bracket"] = k5
        k6 = []
        for grp, nm in ((uk.APF_IPP, "APF IPP"), (uk.APF_FACE, "APF face")):
            for a in range(5):
                k6 += D.amount(f"{nm}[{a},{a+1})", grp, a, a + 1) + first_moment(D, f"t*{nm}[{a},{a+1})", grp, a, a + 1)
        c["K6 APF annual amounts + mean dates y1-5"] = k6
        terms = _terms(uk.CONS_ALL, mk_amount(led.supports, 0, 1, uk.REFIX_CONS))
        v = evaluate(terms, led.atoms, led.supports)
        c["K7 share refixing <1y (consolidated)"] = [Moment("refix[0,1)", terms, v, v)]
    return c


def objective(spec) -> dict:
    led = ledger(spec["country"], spec["perimeter"], M_GILT.get(spec.get("variant", "baseline")))
    sc = SCENARIOS[spec["scenario"]]
    a, b = WINDOWS[spec["window"]]
    if spec.get("kernel", "first") == "iai":
        from .experiments import kernel_iai
        return kernel_iai(sc, spec["window"], Q(45, 1000), led.supports, led.perimeter)
    if spec.get('kernel') == 'recursive_annual':
        from .experiments import kernel_recursive_annual
        return kernel_recursive_annual(sc, spec['window'], Q(45,1000), led.supports, led.perimeter)
    return kernel(sc, a, b, led.supports, led.perimeter)


def build(spec) -> Problem:
    variant = spec.get("variant", "baseline")
    led = ledger(spec["country"], spec["perimeter"], M_GILT.get(variant))
    mom, cpl = _sets(spec["country"], spec["perimeter"], variant)[spec["set"]]
    obj = objective(spec)
    if spec.get("mode", "bound") == "coupled":
        base = Problem(supports=led.supports, objective=obj, moments=list(mom), couplings=list(cpl), grid=DAY)
        cand = candidates(spec["country"], spec["perimeter"])[spec["candidate"]] if spec.get("candidate") else []
        return coupled(base, [(m.name, m.terms) for m in cand])
    extra = candidates(spec["country"], spec["perimeter"])[spec["candidate"]] if spec.get("candidate") else []
    return Problem(supports=led.supports, objective=obj, moments=list(mom) + list(extra), couplings=list(cpl), grid=DAY)


def truth_and_feasibility(spec):
    from .model import truth_feasible
    variant = spec.get("variant", "baseline")
    led = ledger(spec["country"], spec["perimeter"], M_GILT.get(variant))
    obj = objective(spec)
    t = evaluate(obj, led.atoms, led.supports)
    pr = build({**spec, "mode": "bound"})
    bad = truth_feasible(led, pr.moments, pr.couplings)
    return t, bad
