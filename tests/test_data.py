import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ddb.data_uk import VALUATION_DATE, load_uk  # noqa: E402
from ddb.us import SUBTOTAL, load_us  # noqa: E402


def _isin_ok(s):
    digits = "".join(str(int(ch, 36)) for ch in s[:-1])
    tot = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d) * (2 if i % 2 == 0 else 1)
        tot += n // 10 + n % 10
    return (10 - tot % 10) % 10 == int(s[-1])


def test_gilt_list_integrity():
    p = load_uk()
    g = p.gilts
    assert len(g) == 105 and g["isin"].is_unique
    assert all(_isin_ok(s) for s in g["isin"])
    def br(t):
        return "Ultra-Short" if t < 3 else "Short" if t < 7 else "Medium" if t < 15 else "Long"
    for r in g.itertuples():
        assert br((r.redemption - VALUATION_DATE).days / 365.25) == r.dmo_bracket, r.name
    assert (g.uplifted >= g.nominal - 1e-9).all()
    assert abs(g[g.kind == "conv"].nominal.sum() - 2231440.98662887) < 1e-3


def test_apf_and_bills():
    p = load_uk()
    g = p.gilts
    held = g[g.apf_nominal > 0]
    assert len(held) == 40 and (held.kind == "conv").all() and (held.apf_nominal <= held.nominal).all()
    assert abs(held.apf_ipp.sum() / 1e3 - 488.1492748413116) < 1e-6
    assert abs(p.tbills.amount.sum() - p.tbill_stock) < 1e-6 and p.tbill_stock == 94193.0
    assert (p.tbills.tau <= 0.5).all()


def test_us_reconciles_to_mspd_subtotals():
    rows = load_us()
    for c, sub in SUBTOTAL.items():
        assert abs(sum(x["amount"] for x in rows if x["cls"] == c) - sub) < 0.5
