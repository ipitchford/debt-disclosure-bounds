"""Figures for the paper (PDF + PNG) from results/*.json and the UK ledger."""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
OUT = ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": INK2, "axes.labelcolor": INK,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "savefig.bbox": "tight", "savefig.dpi": 200,
})


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png")
    plt.close(fig)


def fig_intervals(path, perimeter, scenario, sets, labels, name, unit="£bn"):
    rows = json.load(open(path))
    years = ["y1", "y2", "y3", "y4", "y5"]
    fig, axes = plt.subplots(1, len(sets), figsize=(1.55 * len(sets) + 0.6, 2.6), sharey=True)
    ymax = 0
    for ax, s, lab in zip(axes, sets, labels):
        rr = {r["window"]: r for r in rows if r["perimeter"] == perimeter and r["scenario"] == scenario and r["set"] == s}
        for i, y in enumerate(years):
            r = rr[y]
            ax.vlines(i + 1, r["lo"], r["hi"], color=S1, linewidth=5, alpha=0.85, capstyle="round")
            ax.plot(i + 1, r["truth"], marker="o", ms=4.2, color=INK, mec="white", mew=0.8, zorder=3)
            ymax = max(ymax, r["hi"])
        ax.set_title(lab, fontsize=8.2, color=INK, loc="left")
        ax.set_xticks(range(1, 6))
        ax.set_xlim(0.4, 5.6)
        ax.set_xlabel("year after shock")
    axes[0].set_ylabel(f"extra interest, {unit} per year")
    for ax in axes:
        ax.set_ylim(0, ymax * 1.05)
    fig.legend(handles=[plt.Line2D([], [], color=S1, lw=5, label="identified interval"),
                        plt.Line2D([], [], color=INK, marker="o", lw=0, ms=4.5, label="instrument-level value")],
               loc="upper right", ncol=2, bbox_to_anchor=(1.0, 1.08))
    save(fig, name)


def fig_value(path, perimeter, base, panels, name):
    rows = json.load(open(path))
    fig, axes = plt.subplots(1, len(panels), figsize=(3.4 * len(panels), 2.9))
    if len(panels) == 1:
        axes = [axes]
    for ax, (sc, wk, title) in zip(axes, panels):
        rr = [r for r in rows if r["perimeter"] == perimeter and r["set"] == base and r["scenario"] == sc and r["window"] == wk]
        labs = [r["candidate_label"].split(" ", 1)[1] if r["candidate_label"][0] == "K" else "base set only" for r in rr]
        y = list(range(len(rr)))[::-1]
        h = 0.36
        ax.barh([v + h / 2 for v in y], [r["width"] for r in rr], height=h, color=S1, label="with realised values")
        ax.barh([v - h / 2 for v in y], [r["worst_width"] for r in rr], height=h, color=S2, label="worst case (guaranteed)")
        ax.set_yticks(y)
        ax.set_yticklabels(labs)
        ax.set_title(title, fontsize=8.2, loc="left", color=INK)
        ax.set_xlabel("width of identified interval, £bn")
        ax.grid(axis="y", visible=False)
    fig.legend(handles=axes[0].get_legend_handles_labels()[0], labels=axes[0].get_legend_handles_labels()[1],
               loc="upper right", ncol=2, bbox_to_anchor=(1.0, 1.07))
    for ax in axes[1:]:
        ax.set_yticklabels([])
    save(fig, name)


def fig_profile(name):
    from ddb.data_uk import load_uk, SHOCK_DATE
    p = load_uk()
    g = p.gilts.copy()
    g["year"] = ((g.redemption - SHOCK_DATE).apply(lambda d: d.days) / 365.25).astype(int)
    years = range(0, 48)
    priv = [((g.kind == "conv") & (g.year == y)).astype(float).mul(g.nominal - g.apf_nominal).sum() / 1e3 for y in years]
    apf = [((g.kind == "conv") & (g.year == y)).astype(float).mul(g.apf_nominal).sum() / 1e3 for y in years]
    ilg = [((g.kind == "ilg") & (g.year == y)).astype(float).mul(g.uplifted).sum() / 1e3 for y in years]
    bills = [p.tbill_stock / 1e3 if y == 0 else 0 for y in years]
    fig, ax = plt.subplots(figsize=(6.8, 2.5))
    bottom = [0] * len(years)
    for vals, col, lab in ((bills, S4, "Treasury bills"), (priv, S1, "conventional, privately held"),
                           (apf, S2, "conventional, held by the APF (face)"), (ilg, S3, "index-linked (uplifted)")):
        ax.bar(list(years), vals, bottom=bottom, color=col, width=0.82, label=lab, edgecolor="white", linewidth=0.4)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xlabel("residual maturity, whole years from 13 October 2026")
    ax.set_ylabel("£bn")
    ax.set_xlim(-0.8, 47.8)
    ax.legend(ncol=4, loc="lower left", bbox_to_anchor=(0.0, 1.0), fontsize=7.6, handlelength=1.2, columnspacing=1.0)
    ax.grid(axis="x", visible=False)
    save(fig, name)


if __name__ == "__main__":
    R = ROOT / "results"
    fig_profile("fig1_uk_profile")
    fig_intervals(R / "uk_bounds.json", "consolidated", "all",
                  ["D0 headline", "D1 DMO brackets", "D2 GFS residual maturity", "D3 MTDS indicators", "D5 DMO + APF by bracket", "D* annual amounts+timing"],
                  ["Headline", "DMO brackets", "GFS buckets", "MTDS indicators", "DMO + APF brackets", "Annual profile"],
                  "fig2_uk_consolidated_all")
    fig_intervals(R / "uk_bounds.json", "gross", "gilt",
                  ["D0 headline", "D1 DMO brackets", "D2 GFS residual maturity", "D3 MTDS indicators", "D* annual amounts+timing"],
                  ["Headline", "DMO brackets", "GFS buckets", "MTDS indicators", "Annual profile"],
                  "fig3_uk_gross_gilt")
    fig_value(R / "uk_value_of_disclosure.json", "consolidated", "D1 DMO brackets",
              [("all", "cum5", "All rates +1pp, five-year total"), ("short", "cum5", "Short rates +1pp, five-year total")],
              "fig4_uk_value_of_disclosure")
    fig_intervals(R / "us_bounds.json", "gross", "all",
                  ["U0 headline", "U1 MSPD by security type", "U2 GFS residual maturity", "U3 MTDS indicators", "U* annual amounts+timing"],
                  ["Headline", "By security type", "GFS buckets", "MTDS indicators", "Annual profile"],
                  "fig5_us_all", unit="$bn")
    print("figures written to", OUT)
