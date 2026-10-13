"""UK ledger and the catalogue of disclosure sets evaluated in the paper."""
from __future__ import annotations

from fractions import Fraction as Q

from .data_uk import SHOCK_DATE, load_uk
from .model import Discloser, Ledger, apf_couplings, g_, ilg_couplings
from .pa import q

M_GILT = Q(50)      # declared maximum residual maturity (longest gilt: 47.0 years)
M_BILL = Q(1, 2)    # Treasury bills are issued at tenors of at most six months
# Bank of England banknotes on the balance sheet, September 2026 ("around GBP 99 billion"; Bank Insights,
# "The promise to pay: what backs banknotes?", 2026). They are backed by the Issue Deposit, which is
# backed by the loan to the APF; consolidating the whole Bank, that part of the QE loan costs nothing.
NOTES = Q(99000)

# Bounds on initial purchase proceeds per unit face for QE holdings, from the extreme weighted-average
# accepted prices in all APF gilt purchase operations 2009-2022 (74.9 and 235.3 per 100 face);
# widened to round numbers.
APF_R_LO, APF_R_HI = Q(1, 2), Q(5, 2)
# Bounds on the index ratio (uplifted / nominal) of index-linked gilts.
ILG_U_LO, ILG_U_HI = Q(1), Q(7, 2)


def days_to_years(days: int) -> Q:
    return Q(days * 4, 1461)


def build_ledger(perimeter: str, m_gilt: Q = M_GILT) -> Ledger:
    p = load_uk()
    atoms: dict[str, list] = {}

    def add(c, t, w):
        if w > 0:
            atoms.setdefault(c, []).append((t, q(w)))

    for r in p.gilts.itertuples():
        t = days_to_years((r.redemption - SHOCK_DATE).days)
        if r.kind == "conv":
            add("conv", t, r.nominal)
            if perimeter.startswith("consolidated"):
                add("apf_face", t, r.apf_nominal)
                add("apf_ipp", t, r.apf_ipp)
        else:
            c = "ilg3" if abs(r.lag - 0.25) < 1e-9 else "ilg8"
            add(c, t, r.uplifted)
            add(c + "n", t, r.nominal)
    for r in p.tbills.itertuples():
        t = max(Q(0), days_to_years((r.redemption - SHOCK_DATE).days))
        add("bill", t, r.amount)
    supports = {c: q(m_gilt) for c in ("conv", "ilg3", "ilg8", "ilg3n", "ilg8n")}
    supports["bill"] = M_BILL
    if perimeter.startswith("consolidated"):
        supports["apf_face"] = q(m_gilt)
        supports["apf_ipp"] = q(m_gilt)
    if perimeter == "consolidated_bank":
        supports["notes"] = q(m_gilt)
        atoms["notes"] = [(Q(0), NOTES)]
    for c, lst in atoms.items():
        for t, _ in lst:
            if not (0 <= t <= supports[c]):
                raise ValueError(f"{c} atom at {float(t)} outside support")
    return Ledger(atoms=atoms, supports=supports, perimeter=perimeter)


# Groups -----------------------------------------------------------------------------------------
CONV = g_(conv=1)
ILG = g_(ilg3=1, ilg8=1)
ILGN = g_(ilg3n=1, ilg8n=1)
GILTS = g_(conv=1, ilg3=1, ilg8=1)
BILLS = g_(bill=1)
ALL = g_(conv=1, ilg3=1, ilg8=1, bill=1)
APF_IPP = g_(apf_ipp=1)
APF_FACE = g_(apf_face=1)
# Consolidated refixing view: privately held fixed-rate debt refixes at maturity, QE reserves at once.
CONS_ALL = g_(conv=1, apf_face=-1, ilg3=1, ilg8=1, bill=1, apf_ipp=1)
REFIX_CONS = {"apf_ipp": 0}

DMO_EDGES = [0, 3, 7, 15]           # ultra-short, short, medium, long
ECB_EDGES = [0, 1, 5]               # <=1y, 1-5y, >5y


def _buckets(D: Discloser, prefix, group, edges):
    out = []
    for a, b in zip(edges, edges[1:] + [None]):
        out += D.amount(f"{prefix}[{a},{b if b is not None else 'max'})", group, a, b)
    return out


def _bucket_means(D: Discloser, prefix, group, edges):
    out = []
    for a, b in zip(edges, edges[1:] + [None]):
        out += D.mean(f"mean {prefix}[{a},{b if b is not None else 'max'})", group, a, b)
    return out


def disclosure_sets(led: Ledger, precision: dict | None = None, apf_r=None) -> dict[str, tuple[list, list]]:
    """Return {name: (moments, couplings)} for the disclosure sets of the paper."""
    D = Discloser(led, precision)
    cons = led.perimeter.startswith("consolidated")
    apf_r = apf_r or (APF_R_LO, APF_R_HI)
    cpl = apf_couplings(*apf_r) if cons else []

    # Without any APF information, the consolidated perimeter is not identified at all; every
    # consolidated set below therefore discloses at least the APF totals, as the Bank does.
    apf_tot = (D.amount("APF IPP total", APF_IPP) + D.amount("APF face total", APF_FACE)) if cons else []
    bills_tot = D.amount("bills total", BILLS)

    sets: dict[str, tuple[list, list]] = {}
    # D0 headline: gilt total and average maturity; bill stock.
    d0 = D.amount("gilts total", GILTS) + D.mean("gilt WAM", GILTS) + D.amount("IL total", ILG) + bills_tot
    sets["D0 headline"] = (d0 + apf_tot, cpl)
    # D1 DMO portfolio breakdown: conventional and IL by DMO maturity bracket.
    d1 = _buckets(D, "conv", CONV, DMO_EDGES) + _buckets(D, "IL", ILG, DMO_EDGES) + D.mean("gilt WAM", GILTS) + bills_tot
    sets["D1 DMO brackets"] = (d1 + apf_tot, cpl)
    # D2 ECB/Eurostat GFS: all marketable debt by residual maturity and average residual maturity.
    d2 = _buckets(D, "debt", ALL, ECB_EDGES) + D.mean("debt ARM", ALL) + D.amount("IL total", ILG)
    sets["D2 GFS residual maturity"] = (d2 + apf_tot, cpl)
    # D3 MTDS cost-risk indicators.
    d3 = (D.amount("debt total", ALL) + D.mean("ATM", ALL) + D.share("matures<1y", ALL, ALL, 0, 1)
          + D.share("IL share", ILG, ALL) + bills_tot)
    if cons:
        d3 += (D.mean("ATR", CONS_ALL, refix=REFIX_CONS)
               + D.share("refixes<1y", CONS_ALL, CONS_ALL, 0, 1, refix=REFIX_CONS))
    sets["D3 MTDS indicators"] = (d3 + apf_tot, cpl)
    if cons:
        # D4 = D1 + APF totals (already included); D5 = D1 + APF by DMO bracket; D6 = D1 + APF by bucket means.
        d5 = d1 + _buckets(D, "APF IPP", APF_IPP, DMO_EDGES) + _buckets(D, "APF face", APF_FACE, DMO_EDGES)
        sets["D5 DMO + APF by bracket"] = (d5, cpl)
    # D* sufficient: annual refixing amounts and mean refix dates for years 1..5, then totals.
    yrs = [0, 1, 2, 3, 4, 5]
    dstar = []
    for grp, nm in ((CONV, "conv"), (ILG, "IL"), (BILLS, "bills")):
        for a, b in zip(yrs, yrs[1:]):
            if grp is BILLS and a >= 1:
                continue
            dstar += D.amount(f"{nm}[{a},{b})", grp, a, b)
            if D._value({c: _ind(led, c, a, b) for c in grp if c in led.supports}) > 0:
                dstar += D.mean(f"mean {nm}[{a},{b})", grp, a, b)
        dstar += D.amount(f"{nm}[5,max)", grp, 5, None) if grp is not BILLS else []
    dstar += D.amount("IL3 total", g_(ilg3=1)) + D.amount("IL8 total", g_(ilg8=1))
    if cons:
        for grp, nm in ((APF_IPP, "APF IPP"), (APF_FACE, "APF face")):
            for a, b in zip(yrs, yrs[1:]):
                dstar += D.amount(f"{nm}[{a},{b})", grp, a, b)
                if D._value({c: _ind(led, c, a, b) for c in grp}) > 0:
                    dstar += D.mean(f"mean {nm}[{a},{b})", grp, a, b)
            dstar += D.amount(f"{nm}[5,max)", grp, 5, None)
    sets["D* annual amounts+timing"] = (dstar, cpl)
    if "notes" in led.supports:   # the Bank publishes banknotes in circulation weekly
        notes = D.amount("banknotes total", {"notes": Q(1)})
        sets = {k: (m + notes, c) for k, (m, c) in sets.items()}
    return sets


def _ind(led, c, a, b):
    from .pa import indicator
    return indicator(a, min(q(b), led.supports[c]))
