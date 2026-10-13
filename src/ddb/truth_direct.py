"""Second evaluator of instrument-level values (code path A).

It re-reads the raw source files with its own parsers (regular expressions for the DMO XML, the
xlsx zip container for the Bank of England table, its own pass over the DMO bill table, plain JSON
for the MSPD), and computes the first-order cost with dates and floats. It shares no code with
data_uk / us / model / lp. It does share the modelling conventions (perimeter, bill
reconstruction rule, frozen-principal inflation term), so it checks implementation, not assumptions.
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import re
import zipfile
from pathlib import Path

import xlrd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
YEAR = 365.25
UK_SHOCK = dt.date(2026, 10, 13)
US_SHOCK = dt.date(2026, 10, 1)
NOTES_GBPM = 99000.0


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s[:10])


@functools.lru_cache(maxsize=1)
def raw_gilts() -> list[dict]:
    txt = (RAW / "manual" / "dmo_D1A_gilts_in_issue_20261012.xml").read_text(encoding="utf-8")
    out = []
    for el in re.findall(r"<View_GILTS_IN_ISSUE\s+([^>]*?)/>", txt):
        a = dict(re.findall(r'(\w+)="([^"]*)"', el))
        typ = a["INSTRUMENT_TYPE"].strip()
        out.append(dict(isin=a["ISIN_CODE"], red=_d(a["REDEMPTION_DATE"]), nominal=float(a["TOTAL_AMOUNT_IN_ISSUE"]),
                        uplifted=float(a["TOTAL_AMOUNT_INCLUDING_IL_UPLIFT"]),
                        lag=None if typ == "Conventional" else (0.25 if "3 months" in typ else 8 / 12)))
    return out


@functools.lru_cache(maxsize=1)
def raw_apf() -> dict[dt.date, tuple[float, float]]:
    """Per-redemption-date (face, IPP) in GBP m, read from the xlsx XML without openpyxl."""
    z = zipfile.ZipFile(RAW / "boe_table-for-website.xlsx")
    names = z.namelist()
    wb = z.read("xl/workbook.xml").decode()
    rels = z.read("xl/_rels/workbook.xml.rels").decode()
    rid = re.search(r'<sheet[^>]*name="Maturity Profile of APF \(Table\)"[^>]*r:id="(rId\d+)"', wb).group(1)
    target = re.search(rf'Id="{rid}"[^>]*Target="([^"]+)"', rels) or re.search(rf'Target="([^"]+)"[^>]*Id="{rid}"', rels)
    sheet = "xl/" + target.group(1).lstrip("/").replace("xl/", "")
    x = z.read(sheet).decode()
    out = {}
    for row in re.findall(r"<row[^>]*>(.*?)</row>", x, flags=re.S):
        cells = dict(re.findall(r'<c r="([A-Z]+)\d+"[^>]*>(?:<f>.*?</f>)?<v>([^<]*)</v>', row))
        if "B" in cells and "C" in cells and "D" in cells:
            try:
                serial = float(cells["B"])
            except ValueError:
                continue
            if serial < 40000:
                continue
            date = dt.date(1899, 12, 30) + dt.timedelta(days=int(serial))
            out[date] = (float(cells["C"]) * 1e3, float(cells["D"]) * 1e3)
    assert "xl/sharedStrings.xml" in names
    return out


@functools.lru_cache(maxsize=1)
def raw_bills() -> list[tuple[dt.date, float]]:
    sh = xlrd.open_workbook(str(RAW / "manual" / "dmo_tbill_issuance_and_stock_20261013.xls")).sheet_by_index(0)
    months, fy, stock = [], None, None
    for r in range(sh.nrows):
        v = sh.row_values(r)
        lab = str(v[0]).strip()
        m = re.fullmatch(r"(\d{4})-\d{2}", lab)
        if m:
            fy = int(m.group(1))
            continue
        if fy is None or lab[:3] not in ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"):
            continue
        mon = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].index(lab[:3]) + 1
        yr = fy if mon >= 4 else fy + 1
        if (yr, mon) == (2026, 9):
            stock = float(v[7])
        months.append((yr, mon, float(v[1] or 0), float(v[2] or 0), float(v[3] or 0)))
    tr = []
    for yr, mon, m1, m3, m6 in months:
        for k, amt in ((1, m1), (3, m3), (6, m6)):
            mm = mon + k
            mat = dt.date(yr + (mm - 1) // 12, (mm - 1) % 12 + 1, 15)
            if amt > 0 and dt.date(yr, mon, 15) <= dt.date(2026, 9, 30) < mat:
                tr.append((mat, amt))
    scale = stock / sum(a for _, a in tr)
    return [(d, a * scale) for d, a in tr]


def _after(t, a, b):
    return max(0.0, b - max(a, t))


def _before(t, a, b):
    return max(0.0, min(b, t) - a)


def uk_truth(perimeter: str, dg: float, ds: float, dpi: float, a: float, b: float) -> float:
    apf = raw_apf() if perimeter.startswith("consolidated") else {}
    total = 0.0
    for g in raw_gilts():
        t = (g["red"] - UK_SHOCK).days / YEAR
        if g["lag"] is None:
            face, ipp = apf.get(g["red"], (0.0, 0.0))
            total += (g["nominal"] - face) * dg * _after(t, a, b)
            total += ipp * (ds * _before(t, a, b) + dg * _after(t, a, b))
        else:
            total += g["uplifted"] * (dg * _after(t, a, b) + dpi * _after(g["lag"], a, b))
    for mat, amt in raw_bills():
        total += amt * ds * _after(max(0.0, (mat - UK_SHOCK).days / YEAR), a, b)
    if perimeter == "consolidated_bank":
        total -= NOTES_GBPM * ds * (b - a)
    return total


@functools.lru_cache(maxsize=1)
def raw_us() -> list[tuple[str, dt.date, float]]:
    d = json.loads((RAW / "us" / "mspd_table_3_market_20260930.json").read_text())["data"]
    cls = {"Bills Maturity Value": "bill", "Notes": "note", "Bonds": "bond",
           "Inflation-Protected Securities": "tips", "Floating Rate Notes": "frn"}
    out = []
    for r in d:
        c = cls.get(r["security_class1_desc"])
        if c and re.fullmatch(r"[0-9A-Z]{9}", r["security_class2_desc"]) and re.fullmatch(r"-?[0-9.]+", r["outstanding_amt"]):
            mat = _d(r["maturity_date"])
            if mat > dt.date(2026, 9, 30):
                out.append((c, mat, float(r["outstanding_amt"])))
    return out


def us_truth(dg: float, ds: float, dpi: float, a: float, b: float) -> float:
    total = 0.0
    for c, mat, amt in raw_us():
        t = (mat - US_SHOCK).days / YEAR
        if c in ("note", "bond"):
            total += amt * dg * _after(t, a, b)
        elif c == "tips":
            total += amt * (dg * _after(t, a, b) + dpi * _after(0.25, a, b))
        elif c == "bill":
            total += amt * ds * _after(t, a, b)
        elif c == "frn":
            total += amt * ds * (b - a)
    return total
