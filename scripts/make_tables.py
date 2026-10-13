"""LaTeX tables for the paper, generated from results/*.json and the OBR workbook (no hand-copied numbers)."""
import json
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
OUT = ROOT / "paper" / "tables"
OUT.mkdir(parents=True, exist_ok=True)
OBR_XLSX = ROOT / "data" / "raw" / "manual" / "obr_efo_march2026_detailed_forecast_tables_debt_interest.xlsx"

SETNAME = {
    "D0 headline": "Headline: total, average maturity, IL total, bill stock",
    "D1 DMO brackets": "DMO brackets: conventional and IL by 0--3, 3--7, 7--15, 15+ years",
    "D2 GFS residual maturity": "GFS template: $\\le$1, 1--5, $>$5 years; average residual maturity",
    "D3 MTDS indicators": "MTDS cost-risk indicators",
    "D5 DMO + APF by bracket": "DMO brackets plus APF holdings by bracket",
    "D* annual amounts+timing": "Annual profile: amounts and mean dates, years 1--5",
    "U0 headline": "Headline: total and average maturity",
    "U1 MSPD by security type": "MSPD summary by security type, average maturity",
    "U2 GFS residual maturity": "GFS template: $\\le$1, 1--5, $>$5 years; ARM; TIPS total",
    "U3 MTDS indicators": "MTDS cost-risk indicators",
    "U* annual amounts+timing": "Annual profile by security type, years 1--5",
}
WIN = {"y1": "Year 1", "y2": "Year 2", "y3": "Year 3", "y4": "Year 4", "y5": "Year 5", "cum5": "Years 1--5"}


def f(x, nd=1):
    return f"{x:.{nd}f}"


def interval(r, nd=1):
    if abs(r["hi"] - r["lo"]) < 0.5 * 10 ** (-nd):
        return f"\\textbf{{{f(r['lo'], nd)}}}"
    return f"{f(r['lo'], nd)}--{f(r['hi'], nd)}"


def bounds_panels(path, panels, windows, name, nd=1):
    rows = json.load(open(path))
    lines = ["\\begin{tabular}{l" + "r" * len(windows) + "}", "\\toprule",
             "Disclosure set & " + " & ".join(WIN[w] for w in windows) + " \\\\"]
    for per, sc, title in panels:
        rr = [r for r in rows if r["perimeter"] == per and r["scenario"] == sc]
        sets = []
        for r in rr:
            if r["set"] not in sets:
                sets.append(r["set"])
        lines += ["\\midrule", f"\\multicolumn{{{len(windows) + 1}}}{{l}}{{\\textit{{{title}}}}} \\\\"]
        truth = {r["window"]: r["truth"] for r in rr}
        lines.append("Instrument-level value & " + " & ".join(f(truth[w], nd) for w in windows) + " \\\\")
        for s in sets:
            cells = [interval(next(x for x in rr if x["set"] == s and x["window"] == w), nd) for w in windows]
            lines.append(SETNAME[s] + " & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (OUT / f"{name}.tex").write_text("\n".join(lines) + "\n")


def value_table(path, per, base, targets, name):
    rows = [r for r in json.load(open(path)) if r["perimeter"] == per and r["set"] == base]
    hdr = " & ".join(f"\\multicolumn{{2}}{{c}}{{{t}}}" for _, _, t in targets)
    lines = ["\\begin{tabular}{l" + "rr" * len(targets) + "}", "\\toprule",
             "Reporting package & " + hdr + " \\\\",
             " & " + " & ".join(["realised & worst case"] * len(targets)) + " \\\\", "\\midrule"]
    cands = []
    for r in rows:
        if r["candidate_label"] not in cands:
            cands.append(r["candidate_label"])
    for c in cands:
        cells = []
        for sc, w, _ in targets:
            r = next(x for x in rows if x["candidate_label"] == c and x["scenario"] == sc and x["window"] == w)
            cells += [f(r["width"]), f(r["worst_width"])]
        lab = "none (base set only)" if c.startswith("(") else c.split(" ", 1)[1].replace("<", "$<$")
        lines.append(lab + " & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (OUT / f"{name}.tex").write_text("\n".join(lines) + "\n")


def robustness_table(name):
    rows = json.load(open(R / "uk_robustness.json"))
    cols = [("gross", "D0 headline", "all", "y1", r"\shortstack[l]{Gross\\headline\\year 1}"),
            ("consolidated", "D1 DMO brackets", "all", "cum5", r"\shortstack[l]{IPP-funded\\DMO brackets\\years 1--5}"),
            ("consolidated", "D2 GFS residual maturity", "all", "y1", r"\shortstack[l]{IPP-funded\\GFS template\\year 1}")]
    variants = []
    for r in rows:
        v = r.get("variant_label")
        if v and v not in variants:
            variants.append(v)
    lines = [r"\begin{tabular}{p{.34\textwidth}lll}", "\\toprule",
             "Variant & " + " & ".join(c[4] for c in cols) + " \\\\", "\\midrule"]
    truths = []
    for per, s, sc, w, _ in cols:
        t = next(r["truth"] for r in rows if r["perimeter"] == per and r["scenario"] == sc and r["window"] == w
                 and r.get("kernel", "first") == "first")
        truths.append(f(t, 2))
    lines.append("Instrument-level value & " + " & ".join(truths) + " \\\\")
    for v in variants:
        cells = []
        for per, s, sc, w, _ in cols:
            r = [x for x in rows if x.get("variant_label") == v and x["perimeter"] == per and x["set"] == s
                 and x["scenario"] == sc and x["window"] == w]
            if not r:
                cells.append("--")
                continue
            r = r[0]
            if r["lo"] is None:
                cells.append("LP failed")
                continue
            mark = ""
            if r["status"].startswith("mis-specified"):
                mark = "$^\\ddagger$" if r["contains_true_value"] else "$^{\\ddagger\\dagger}$"
            elif r["status"] != "covers":
                mark = "$^\\dagger$"
            cell = f"{f(r['lo'], 2)}--{f(r['hi'], 2)}{mark}"
            if r.get("kernel") == "iai":
                cell += f" ({f(r['truth'], 2)})"
            cells.append(cell)
        lab = v.replace("£", "\\pounds").replace("[", "$[").replace("]", "]$").replace("%", "\\%")
        lines.append(lab + " & " + " & ".join(cells) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (OUT / f"{name}.tex").write_text("\n".join(lines) + "\n")


def obr_values():
    wb = openpyxl.load_workbook(OBR_XLSX, read_only=True, data_only=True)
    ws = wb["5.1"]
    out = {}
    for row in ws.iter_rows(values_only=True):
        vals = [x for x in row if x is not None]
        if vals and isinstance(vals[0], str) and vals[0].startswith("1 percentage point increase in"):
            for key, lab in (("gilt", "gilt rates"), ("short", "short rates"), ("infl", "inflation")):
                if lab in vals[0]:
                    out[key] = [float(x) for x in vals[1:6]]
    if set(out) != {"gilt", "short", "infl"}:
        raise ValueError(f"Unexpected OBR scenario inventory: {sorted(out)}")
    return out


def obr_table(name):
    obr = obr_values()
    per = json.load(open(R / "uk_perimeter.json"))
    rows = json.load(open(R / "uk_bounds.json"))
    lab = {"gilt": "Gilt yields +1pp", "short": "Short rates +1pp", "infl": "RPI inflation +1pp"}
    lines = ["\\begin{tabular}{llrrrrr}", "\\toprule", " & & 1 & 2 & 3 & 4 & 5 \\\\", "\\midrule"]
    for sc in ("short", "gilt", "infl"):
        ours = [next(r["truth"] for r in rows if r["perimeter"] == "consolidated" and r["scenario"] == sc
                     and r["window"] == f"y{k}" and r["set"] == "D0 headline") for k in range(1, 6)]
        lines.append(f"{lab[sc]} & OBR, fiscal years 2026-27 to 2030-31 & " + " & ".join(f(x, 2) for x in obr[sc]) + " \\\\")
        lines.append(" & Synthetic IPP-funded & " + " & ".join(f(x, 2) for x in ours) + " \\\\")
        if sc == "short":
            for p in per:
                if p["scenario"] == "short" and p["perimeter"] != "Synthetic IPP-funded":
                    nm = p["perimeter"]
                    lines.append(" & " + nm + " & " + " & ".join(f(p[f"y{k}"], 2) for k in range(1, 6)) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (OUT / f"{name}.tex").write_text("\n".join(lines) + "\n")


def perimeter_table(name):
    per = json.load(open(R / "uk_perimeter.json"))
    lines = ["\\begin{tabular}{llrrrrrr}", "\\toprule",
             "Perimeter & Shock & Year 1 & Year 2 & Year 3 & Year 4 & Year 5 & Years 1--5 \\\\", "\\midrule"]
    for p in per:
        lines.append(f"{p['perimeter']} & {'all rates' if p['scenario'] == 'all' else 'short rates'} & "
                     + " & ".join(f(p[w], 2) for w in ("y1", "y2", "y3", "y4", "y5", "cum5")) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (OUT / f"{name}.tex").write_text("\n".join(lines) + "\n")


def precision_table(name):
    rows = json.load(open(R / "uk_k9_precision.json"))
    lines = ["\\begin{tabular}{lrrr}", "\\toprule",
             "Mean maturity of debt due within a year, published & Gross & Synthetic IPP-funded \\\\", "\\midrule"]
    labels = []
    for r in rows:
        key = "exactly" if r["candidate_label"].startswith("K9") else r["candidate_label"].split("rounded to ")[1]
        if key not in labels:
            labels.append(key)
    lines[0] = "\\begin{tabular}{lll}"
    for key in labels:
        cells = []
        for per in ("gross", "consolidated"):
            r = next(x for x in rows if x["perimeter"] == per and
                     (x["candidate_label"].startswith("K9") if key == "exactly" else x["candidate_label"].endswith(key)))
            cells.append(f"{f(r['lo'], 3)}--{f(r['hi'], 3)} (width {f(r['hi'] - r['lo'], 3)})")
        lines.append(("exactly" if key == "exactly" else f"rounded to {key}") + " & " + " & ".join(cells) + " \\\\")
    tr = {per: next(x["truth"] for x in rows if x["perimeter"] == per) for per in ("gross", "consolidated")}
    lines.append(f"Instrument-level value & {f(tr['gross'], 3)} & {f(tr['consolidated'], 3)} \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    (OUT / f"{name}.tex").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    W4 = ["y1", "y3", "y5", "cum5"]
    bounds_panels(R / "uk_bounds.json",
                  [("gross", "gilt", "A. Gross marketable debt, gilt yields +1pp"),
                   ("consolidated", "all", "B. Synthetic IPP-funded, all rates +1pp"),
                   ("consolidated", "short", "C. Synthetic IPP-funded, short rates +1pp")],
                  W4, "tab_uk_bounds")
    bounds_panels(R / "us_bounds.json",
                  [("gross", "all", "A. All rates +1pp"), ("gross", "short", "B. Short rates +1pp")],
                  W4, "tab_us_bounds", nd=0)
    value_table(R / "uk_value_of_disclosure.json", "consolidated", "D1 DMO brackets",
                [("all", "y1", "All rates, year 1"), ("all", "cum5", "All rates, years 1--5"),
                 ("short", "cum5", "Short rates, years 1--5")], "tab_uk_value_d1")
    value_table(R / "uk_value_of_disclosure.json", "gross", "D2 GFS residual maturity",
                [("all", "y1", "All rates, year 1"), ("all", "cum5", "All rates, years 1--5"),
                 ("gilt", "y5", "Gilt yields, year 5")], "tab_uk_value_d2_gross")
    robustness_table("tab_robustness")
    obr_table("tab_obr")
    perimeter_table("tab_perimeter")
    precision_table("tab_precision")
    print("tables written to", OUT)
