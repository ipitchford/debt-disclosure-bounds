"""Instrument-level values under alternative consolidation perimeters -> results/uk_perimeter.json.

- Synthetic IPP-funded: a hypothetical liability equal to the initial purchase proceeds of
  retained holdings pays Bank Rate. This is not the observed APF loan or a validated OBR perimeter.
- Synthetic banknote allocation: about GBP 99bn of banknotes is assigned as zero-cost funding.
  The allocation is a scenario assumption, not a reconstruction of consolidated cash flows.
- Assumed sales (short-rate shock only): a GBP 146.5bn purchase-proceeds block is reduced at
  GBP 20bn a year from 1 April 2027, pro rata. The funding reduction is an imposed convention;
  actual sale proceeds, indemnity settlements and cash balances need not follow it.
"""
import json
import sys
from fractions import Fraction as Q
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ddb.data_uk import SHOCK_DATE  # noqa: E402
from ddb.model import SCENARIOS, truth  # noqa: E402
from ddb.uk import build_ledger  # noqa: E402
import datetime as dt  # noqa: E402

SALES_START = Q((dt.date(2027, 4, 1) - SHOCK_DATE).days * 4, 1461)
SALES_RATE = Q(20000)        # GBP m per year, purchase-proceeds terms
BLOCK = Q(146500)


def sold_integral(a, b):
    """int_a^b of the cumulative amount sold by time tau (capped at the block)."""
    # exact piecewise integral: sold(tau) = min(BLOCK, SALES_RATE * (tau - start)^+), linear then flat
    cap = SALES_START + BLOCK / SALES_RATE
    def F(x):  # antiderivative of sold(tau)
        if x <= SALES_START:
            return Q(0)
        if x <= cap:
            return SALES_RATE * (x - SALES_START) ** 2 / 2
        return SALES_RATE * (cap - SALES_START) ** 2 / 2 + BLOCK * (x - cap)
    return F(Q(b)) - F(Q(a))


out = []
wins = {"y1": (0, 1), "y2": (1, 2), "y3": (2, 3), "y4": (3, 4), "y5": (4, 5), "cum5": (0, 5)}
for per, label in (("consolidated", "Synthetic IPP-funded"), ("consolidated_bank", "Synthetic banknote allocation")):
    led = build_ledger(per)
    for sk in ("all", "short"):
        sc = SCENARIOS[sk]
        row = {"perimeter": label, "scenario": sk}
        for wk, (a, b) in wins.items():
            row[wk] = float(truth(led, sc, a, b)) / 1e3
        out.append(row)
        if sk == "short":
            row2 = {"perimeter": label + ", with assumed sales", "scenario": sk}
            for wk, (a, b) in wins.items():
                row2[wk] = float(truth(led, sc, a, b) - sc.ds * sold_integral(a, b)) / 1e3
            out.append(row2)
(ROOT / "results" / "uk_perimeter.json").write_text(json.dumps(out, indent=1))
for r in out:
    print(r["perimeter"][:55], r["scenario"], [round(r[w], 2) for w in wins])
