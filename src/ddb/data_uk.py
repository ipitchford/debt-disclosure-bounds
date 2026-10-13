"""UK instrument-level data: DMO gilts in issue, DMO Treasury bills, BoE APF holdings.

All amounts are in GBP million. Residual maturities are in years (ACT/365.25) from SHOCK_DATE.
"""
from __future__ import annotations

import datetime as dt
import functools
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import openpyxl
import pandas as pd
import xlrd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

VALUATION_DATE = dt.date(2026, 10, 12)  # DMO close of business
SHOCK_DATE = dt.date(2026, 10, 13)      # first day the shocked rates apply

GILTS_XML = RAW / "manual" / "dmo_D1A_gilts_in_issue_20261012.xml"
TBILL_XLS = RAW / "manual" / "dmo_tbill_issuance_and_stock_20261013.xls"
APF_XLSX = RAW / "boe_table-for-website.xlsx"


def years_between(d0: dt.date, d1: dt.date) -> float:
    return (d1 - d0).days / 365.25


def load_gilts() -> pd.DataFrame:
    root = ET.parse(GILTS_XML).getroot()
    rows = []
    for el in root:
        a = el.attrib
        cob = a["CLOSE_OF_BUSINESS_DATE"][:10]
        if cob != VALUATION_DATE.isoformat():
            raise ValueError(f"unexpected close-of-business date {cob}")
        itype = a["INSTRUMENT_TYPE"].strip()
        red = dt.date.fromisoformat(a["REDEMPTION_DATE"][:10])
        nominal = float(a["TOTAL_AMOUNT_IN_ISSUE"])
        uplifted = float(a["TOTAL_AMOUNT_INCLUDING_IL_UPLIFT"])
        if itype == "Conventional":
            kind, lag = "conv", None
            if abs(uplifted - nominal) > 1e-6:
                raise ValueError(f"conventional gilt with uplift: {a['ISIN_CODE']}")
        elif itype == "Index-linked 3 months":
            kind, lag = "ilg", 3 / 12
        elif itype == "Index-linked 8 months":
            kind, lag = "ilg", 8 / 12
        else:
            raise ValueError(f"unknown instrument type {itype!r}")
        rows.append(
            dict(
                isin=a["ISIN_CODE"],
                name=a["INSTRUMENT_NAME"],
                kind=kind,
                dmo_bracket=a["MATURITY_BRACKET"],
                redemption=red,
                tau=years_between(SHOCK_DATE, red),
                nominal=nominal,
                uplifted=uplifted,
                index_ratio=uplifted / nominal,
                lag=lag,
            )
        )
    df = pd.DataFrame(rows)
    if df["isin"].duplicated().any():
        raise ValueError("duplicate ISIN")
    return df


def load_apf() -> pd.DataFrame:
    """APF holdings per gilt: nominal and initial purchase proceeds (IPP), GBP million."""
    wb = openpyxl.load_workbook(APF_XLSX, read_only=True, data_only=True)
    ws = wb["Maturity Profile of APF (Table)"]
    rows, stock = [], None
    for r in ws.iter_rows(values_only=True):
        if r[0] == "Current stock of holdings":
            stock = float(r[4]) * 1e3
        elif r[0] and isinstance(r[1], dt.datetime):
            rows.append(
                dict(
                    apf_name=str(r[0]).strip(),
                    redemption=r[1].date(),
                    apf_nominal=float(r[2]) * 1e3,
                    apf_ipp=float(r[3]) * 1e3,
                )
            )
    df = pd.DataFrame(rows)
    if stock is None or abs(df.apf_ipp.sum() - stock) > 1.0:
        raise ValueError(f"APF per-gilt IPP {df.apf_ipp.sum():.1f} != headline stock {stock}")
    return df


def load_tbills() -> tuple[float, pd.DataFrame]:
    """Treasury-bill stock at end-September 2026 and a reconstructed maturity profile.

    The DMO table reports monthly issuance by tenor (1, 3, 6 months) and the month-end stock. Bills
    outstanding at end-September are those issued in the preceding tenor-months; each tranche is
    placed at mid-issue-month plus tenor. The reconstruction is scaled to the reported stock (the
    residual reflects ad hoc and other issuance and intra-month timing).
    """
    book = xlrd.open_workbook(TBILL_XLS)
    sh = book.sheet_by_index(0)
    hdr = sh.row_values(4)
    if not str(hdr[7]).startswith("Total Stock Outstanding"):
        raise ValueError("unexpected T-bill table layout")
    # Rows: '2026-27' label then months newest first.
    months, fy = [], None
    for r in range(5, sh.nrows):
        v = sh.row_values(r)
        lab = str(v[0]).strip()
        if len(lab) == 7 and lab[4] == "-":
            fy = int(lab[:4])
            continue
        if fy is None or lab[:3] not in ("Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"):
            continue
        mnum = dt.datetime.strptime(lab[:3], "%b").month
        year = fy if mnum >= 4 else fy + 1
        months.append(dict(year=year, month=mnum, m1=float(v[1] or 0), m3=float(v[2] or 0), m6=float(v[3] or 0), stock=float(v[7] or 0)))
    mdf = pd.DataFrame(months)
    end = mdf[(mdf.year == 2026) & (mdf.month == 9)]
    if len(end) != 1:
        raise ValueError("end-September 2026 T-bill row missing")
    stock = float(end.stock.iloc[0])
    tranches = []
    for _, m in mdf.iterrows():
        issue = dt.date(int(m.year), int(m.month), 15)
        for tenor_m, amt in ((1, m.m1), (3, m.m3), (6, m.m6)):
            if amt <= 0:
                continue
            mat_month = int(m.month) + tenor_m
            mat = dt.date(int(m.year) + (mat_month - 1) // 12, (mat_month - 1) % 12 + 1, 15)
            if issue <= dt.date(2026, 9, 30) < mat:
                tranches.append(dict(issue=issue, tenor_months=tenor_m, redemption=mat, amount=amt))
    tdf = pd.DataFrame(tranches)
    recon = tdf.amount.sum()
    if abs(recon / stock - 1) > 0.02:
        raise ValueError(f"T-bill reconstruction {recon:.0f} vs stock {stock:.0f} differs by >2%")
    tdf["amount"] *= stock / recon
    tdf["tau"] = [max(0.0, years_between(SHOCK_DATE, d)) for d in tdf.redemption]
    return stock, tdf


@dataclass
class UKPortfolio:
    gilts: pd.DataFrame      # one row per gilt, with apf_nominal / apf_ipp merged (0 if not held)
    tbills: pd.DataFrame     # reconstructed T-bill tranches
    tbill_stock: float


@functools.lru_cache(maxsize=1)
def load_uk() -> UKPortfolio:
    g = load_gilts()
    apf = load_apf()
    m = g.merge(apf, on="redemption", how="left", validate="one_to_one")
    held = m.apf_nominal.notna()
    if held.sum() != len(apf):
        raise ValueError("APF holding did not match a unique gilt by redemption date")
    if (m.loc[held, "kind"] != "conv").any():
        raise ValueError("APF holds a non-conventional gilt; model assumes conventional only")
    if (m.loc[held, "apf_nominal"] > m.loc[held, "nominal"] + 1e-6).any():
        raise ValueError("APF holding exceeds amount in issue")
    m[["apf_nominal", "apf_ipp"]] = m[["apf_nominal", "apf_ipp"]].fillna(0.0)
    stock, tb = load_tbills()
    return UKPortfolio(gilts=m, tbills=tb, tbill_stock=stock)


if __name__ == "__main__":
    p = load_uk()
    g = p.gilts
    print(g.groupby("kind")[["nominal", "uplifted", "apf_nominal", "apf_ipp"]].sum().round(0))
    print("T-bill stock", p.tbill_stock, "tranches", len(p.tbills))
    print(p.tbills.groupby("redemption").amount.sum().round(0))
