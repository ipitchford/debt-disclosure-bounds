"""US marketable Treasury debt (MSPD Table 3, CUSIP level, 30 Sep 2026): ledger and disclosure sets.

Perimeter: gross marketable debt only (no consolidation with the Federal Reserve; see the paper).
Amounts in USD million. Notes have original maturity <= 10 years and bonds <= 30 years, so their
residual maturities are bounded by 10 and 30 years respectively; bills by 1 year; FRNs by 2 years.
TIPS principal includes the inflation adjustment.
"""
from __future__ import annotations

import datetime as dt
import functools
import json
from fractions import Fraction as Q
from pathlib import Path

from .model import Discloser, Ledger, g_
from .pa import q

ROOT = Path(__file__).resolve().parents[2]
MSPD = ROOT / "data" / "raw" / "us" / "mspd_table_3_market_20260930.json"
RECORD_DATE = dt.date(2026, 9, 30)
SHOCK_DATE = dt.date(2026, 10, 1)
SUPPORT = {"bill": Q(1), "frn": Q(2), "note": Q(10), "bond": Q(30), "tips": Q(30)}
CLASS = {"Bills Maturity Value": "bill", "Notes": "note", "Bonds": "bond",
         "Inflation-Protected Securities": "tips", "Floating Rate Notes": "frn"}
SUBTOTAL = {"bill": 7118144.89910001, "note": 16281473.051, "bond": 5550990.6094,
            "tips": 2172641.57170234, "frn": 707975.4515}
# Declared exclusion: Federal Financing Bank securities (USD 3,591m), outside Treasury's market borrowing.
EXCLUDED = {"Federal Financing Bank"}
TOTAL_MARKETABLE = 31834878.4434023


def days_to_years(days: int) -> Q:
    return Q(days * 4, 1461)


@functools.lru_cache(maxsize=1)
def load_us() -> list[dict]:
    rows = json.loads(MSPD.read_text())["data"]
    out, seen = [], set()
    excluded = matured = 0.0
    for r in rows:
        if r["record_date"] != RECORD_DATE.isoformat():
            raise ValueError("unexpected record date")
        cls1 = r["security_class1_desc"]
        if cls1 == "Total Marketable":
            if abs(float(r["outstanding_amt"]) - TOTAL_MARKETABLE) > 1e-3:
                raise ValueError("Total Marketable differs from the declared value")
            continue
        if cls1 in EXCLUDED:
            excluded += float(r["outstanding_amt"])
            continue
        if cls1 not in CLASS:
            raise ValueError(f"unexpected marketable category {cls1!r}")
        if r["security_class2_desc"].startswith("Total Matured") and r["outstanding_amt"] not in ("*", "null"):
            matured += float(r["outstanding_amt"])
        c = CLASS.get(cls1)
        cusip = r["security_class2_desc"]
        if c is None or len(cusip) != 9 or r["outstanding_amt"] in ("null", "*", None):
            continue
        if (c, cusip) in seen:
            raise ValueError(f"duplicate CUSIP total {cusip}")
        seen.add((c, cusip))
        mat = dt.date.fromisoformat(r["maturity_date"])
        if mat <= RECORD_DATE:
            continue  # matured, awaiting redemption
        out.append(dict(cls=c, cusip=cusip, maturity=mat, amount=float(r["outstanding_amt"])))
    for c, sub in SUBTOTAL.items():
        tot = sum(x["amount"] for x in out if x["cls"] == c)
        if abs(tot - sub) > 0.5:
            raise ValueError(f"{c}: CUSIP sum {tot:.1f} != MSPD unmatured subtotal {sub:.1f}")
    # Reconcile to Total Marketable: modelled + excluded FFB + matured awaiting redemption (bills' is '*').
    gap = TOTAL_MARKETABLE - sum(x["amount"] for x in out) - excluded - matured
    if abs(gap) > 1.0:
        raise ValueError(f"MSPD total does not reconcile: residual {gap:.1f}m")
    return out


def build_ledger() -> Ledger:
    atoms: dict[str, list] = {}
    for x in load_us():
        t = days_to_years((x["maturity"] - SHOCK_DATE).days)
        if not (0 <= t <= SUPPORT[x["cls"]]):
            raise ValueError(f"{x['cusip']} residual {float(t):.2f} outside {x['cls']} support")
        atoms.setdefault(x["cls"], []).append((t, q(x["amount"])))
    return Ledger(atoms=atoms, supports=dict(SUPPORT), perimeter="gross")


ALL = g_(bill=1, frn=1, note=1, bond=1, tips=1)
FIXED = g_(note=1, bond=1)
REFIX = {"frn": 0}
GFS_EDGES = [0, 1, 5]


def disclosure_sets(led: Ledger, precision: dict | None = None) -> dict[str, tuple[list, list]]:
    D = Discloser(led, precision)
    sets: dict[str, tuple[list, list]] = {}
    tot = D.amount("debt total", ALL)
    wam = D.mean("WAM", ALL)
    sets["U0 headline"] = (tot + wam, [])
    by_type = sum((D.amount(f"{c} total", g_(**{c: 1})) for c in ("bill", "note", "bond", "tips", "frn")), [])
    sets["U1 MSPD by security type"] = (by_type + wam, [])
    gfs = []
    for a, b in zip(GFS_EDGES, GFS_EDGES[1:] + [None]):
        gfs += D.amount(f"debt[{a},{b})", ALL, a, b)
    sets["U2 GFS residual maturity"] = (gfs + D.mean("ARM", ALL) + D.amount("TIPS total", g_(tips=1)), [])
    mtds = (tot + wam + D.mean("ATR", ALL, refix=REFIX) + D.share("matures<1y", ALL, ALL, 0, 1)
            + D.share("refixes<1y", ALL, ALL, 0, 1, refix=REFIX) + D.share("IL share", g_(tips=1), ALL))
    sets["U3 MTDS indicators"] = (mtds, [])
    star = []
    for c in ("bill", "frn", "note", "bond", "tips"):
        grp = g_(**{c: 1})
        for a in range(0, 5):
            if a >= SUPPORT[c]:
                continue
            star += D.amount(f"{c}[{a},{a+1})", grp, a, a + 1)
            if any(a <= t < a + 1 for t, _ in led.atoms.get(c, [])):
                star += D.mean(f"mean {c}[{a},{a+1})", grp, a, a + 1)
        if SUPPORT[c] > 5:
            star += D.amount(f"{c}[5,max)", grp, 5, None)
    sets["U* annual amounts+timing"] = (star, [])
    return sets
