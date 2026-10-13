"""Size of the first-order inflation terms left out of the frozen-principal estimand -> results/uk_inflation_terms.json.

(i) indexed coupons on the extra uplift: real coupon c times the extra principal delta*(tau - lag)^+;
(ii) refinancing at redemption of the extra uplift accumulated to maturity, at a real yield of 1.5%.
Both are first order in the inflation shock; the estimand keeps only principal accrual on the
valuation-date uplifted principal.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ddb.data_uk import SHOCK_DATE, load_uk  # noqa: E402

FRAC = {"": 0.0, "1/8": 0.125, "¼": 0.25, "3/8": 0.375, "½": 0.5, "5/8": 0.625, "¾": 0.75, "7/8": 0.875}


def coupon(name):
    m = re.match(r"\s*(\d+)?\s*(1/8|3/8|5/8|7/8|¼|½|¾)?\s*%", name)
    whole = float(m.group(1)) if m.group(1) else 0.0
    return (whole + FRAC[m.group(2) or ""]) / 100


def integ(f, a, b, n=4000):
    h = (b - a) / n
    return sum(f(a + (i + 0.5) * h) for i in range(n)) * h


p = load_uk()
ilg = p.gilts[p.gilts.kind == "ilg"]
d, ry = 0.01, 0.015
out = {}
for k in range(1, 6):
    main = coup = refi = 0.0
    for r in ilg.itertuples():
        c, U, lag = coupon(r.name), r.uplifted, r.lag
        T = (r.redemption - SHOCK_DATE).days / 365.25
        main += U * d * max(0.0, k - max(k - 1, lag))
        coup += c * U * d * integ(lambda t: max(0.0, t - lag), k - 1, k)
        if T < k:
            refi += ry * U * d * max(0.0, T - lag) * (k - max(k - 1, T))
    out[f"y{k}"] = {"principal_accrual": main / 1e3, "indexed_coupon": coup / 1e3, "refinanced_uplift": refi / 1e3}
(ROOT / "results" / "uk_inflation_terms.json").write_text(json.dumps(out, indent=1))
for k, v in out.items():
    print(k, {a: round(b, 4) for a, b in v.items()}, "omitted share", round((v["indexed_coupon"] + v["refinanced_uplift"]) / v["principal_accrual"], 4))
print({n: coupon(n) for n in ilg.name.head(5)})
