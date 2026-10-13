"""All experiments -> results/*.json (GBP/USD bn) and results/certificates/*.jsonl.gz.

Every bound is built from a specification (src/ddb/specs.py), solved, certified in exact arithmetic
(dual multipliers and an extremal portfolio, both checked inside lp.solve), and stored with its
certificate so that scripts/verify_certificates.py can re-check it without the solver.
"""
import gzip
import json
import sys
import time
from fractions import Fraction as Q
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ddb import specs  # noqa: E402
from ddb.lp import LPError, solve  # noqa: E402

OUT = ROOT / "results"
CERT = OUT / "certificates"
OUT.mkdir(exist_ok=True)
CERT.mkdir(exist_ok=True)


def fr(x: Q) -> str:
    return f"{x.numerator}/{x.denominator}"


class Recorder:
    def __init__(self, name):
        self.name = name
        self.rows = []
        self.f = gzip.open(CERT / f"{name}.jsonl.gz", "wt")

    def solve(self, spec, sense):
        b = solve(specs.build(spec), sense)
        self.f.write(json.dumps({
            "spec": spec, "sense": sense, "value": fr(b.value),
            "primal": [[c, fr(t), s, fr(w)] for c, lst in b.measure.items() for t, s, w in lst],
            "dual": [[i, fr(y)] for i, y in b.dual]}) + "\n")
        return b.value

    def bound(self, spec, extra=None):
        t, bad = specs.truth_and_feasibility(spec)
        row = dict(spec)
        row.update(extra or {})
        row["truth"] = t
        try:
            lo, hi = self.solve(spec, "min"), self.solve(spec, "max")
        except LPError as e:
            row.update(lo=None, hi=None, truth_violations=bad, status=f"LP failed: {e}")
            self.rows.append(row)
            return row
        contains = lo <= t <= hi
        if bad:   # the actual ledger violates the statistics as read: coverage is not guaranteed
            status = "mis-specified; contains true value" if contains else "mis-specified; EXCLUDES true value"
        else:
            status = "covers" if contains else "EXCLUDES TRUTH"
        row.update(lo=lo, hi=hi, truth_violations=bad, contains_true_value=contains, status=status)
        self.rows.append(row)
        return row

    def close(self):
        self.f.close()
        out = []
        for r in self.rows:
            d = {}
            for k, v in r.items():
                if isinstance(v, Q):
                    d[k] = float(v) / 1e3
                    d[k + "_exact"] = fr(v)
                else:
                    d[k] = v
            out.append(d)
        (OUT / f"{self.name}.json").write_text(json.dumps(out, indent=1))


def main():
    t0 = time.time()
    # ---- main bounds tables
    R = Recorder("uk_bounds")
    for per in ("gross", "consolidated", "consolidated_bank"):
        sets = specs._sets("uk", per, "baseline")
        for sk in ("all", "gilt", "short", "infl"):
            for wk in specs.WINDOWS:
                for name in sets:
                    R.bound(dict(country="uk", perimeter=per, set=name, scenario=sk, window=wk))
    R.close()
    assert all(r["status"] == "covers" for r in R.rows), "baseline coverage failure"
    print("uk_bounds", len(R.rows), round(time.time() - t0, 1), flush=True)

    R = Recorder("us_bounds")
    for sk in ("all", "gilt", "short", "infl"):
        for wk in specs.WINDOWS:
            for name in specs._sets("us", "gross", "baseline"):
                R.bound(dict(country="us", perimeter="gross", set=name, scenario=sk, window=wk))
    R.close()
    assert all(r["status"] == "covers" for r in R.rows)
    print("us_bounds", len(R.rows), round(time.time() - t0, 1), flush=True)

    # ---- value of disclosure (ex post and worst case)
    for country, pers, bases in (("uk", ("gross", "consolidated"), ("D0 headline", "D1 DMO brackets", "D2 GFS residual maturity")),
                                 ("us", ("gross",), ("U0 headline", "U1 MSPD by security type", "U2 GFS residual maturity"))):
        R = Recorder(f"{country}_value_of_disclosure")
        for per in pers:
            scen = ("all", "gilt", "short", "infl") if (country == "us" or per == "consolidated") else ("all", "gilt", "infl")
            for base in bases:
                for sk in scen:
                    for wk in ("y1", "y3", "y5", "cum5"):
                        sp = dict(country=country, perimeter=per, set=base, scenario=sk, window=wk)
                        r = R.bound(sp, {"candidate_label": "(base set only)"})
                        r["worst_width"] = R.solve({**sp, "mode": "coupled"}, "max")
                        for cand in [c for c in specs.candidates(country, per) if not c.startswith("R9")]:
                            sp2 = {**sp, "candidate": cand}
                            r = R.bound(sp2, {"candidate_label": cand})
                            r["worst_width"] = R.solve({**sp2, "mode": "coupled"}, "max")
        for r in R.rows:
            if r["lo"] is not None:
                r["width"] = r["hi"] - r["lo"]
        R.close()
        assert all(r["status"] == "covers" for r in R.rows)
        print(f"{country}_value_of_disclosure", len(R.rows), round(time.time() - t0, 1), flush=True)

    # ---- robustness, definitional mismatch, interest on interest
    R = Recorder("uk_robustness")
    targets = [("all", "y1"), ("all", "y5"), ("all", "cum5"), ("gilt", "y5"), ("short", "cum5")]
    focus = ["D0 headline", "D1 DMO brackets", "D2 GFS residual maturity", "D3 MTDS indicators"]
    for per in ("gross", "consolidated"):
        for variant in specs.VARIANTS:
            if per == "gross" and variant in ("apf_obs", "apf_tight", "mm_apf_face"):
                continue
            sets = specs._sets("uk", per, variant)
            for sk, wk in targets:
                if sk == "short" and per == "gross":
                    continue
                for name in focus:
                    if name in sets:
                        R.bound(dict(country="uk", perimeter=per, set=name, scenario=sk, window=wk, variant=variant),
                                {"variant_label": specs.VARIANTS[variant]})
        for sk, wk in targets:
            if sk == "short" and per == "gross":
                continue
            for name in focus + ["D* annual amounts+timing"]:
                R.bound(dict(country="uk", perimeter=per, set=name, scenario=sk, window=wk, kernel="iai"),
                        {"variant_label": "With interest on the extra interest at 4.5%"})
    R.close()
    print("uk_robustness", len(R.rows), round(time.time() - t0, 1), flush=True)

    # ---- one further number at published precision
    R = Recorder("uk_k9_precision")
    for per in ("gross", "consolidated"):
        for cand in [c for c in specs.candidates("uk", per) if c.startswith(("K9", "R9"))]:
            for sk in ("all",):
                sp = dict(country="uk", perimeter=per, set="D2 GFS residual maturity", scenario=sk, window="y1", candidate=cand)
                R.bound(sp, {"candidate_label": cand})
    R.close()
    print("done", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
