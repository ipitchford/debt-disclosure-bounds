"""Compare an independently downloaded DMO report with every model input row."""
import json
import re
import sys
from pathlib import Path
from decimal import Decimal
import xml.etree.ElementTree as ET
import xlrd

ROOT = Path(__file__).resolve().parents[1]
raw = ROOT / 'data/raw'
book = xlrd.open_workbook(raw / 'dmo_official_gilts_20261012.xls')
sheet = book.sheet_by_index(0)
if sheet.cell_value(0, 2) != 'GILTS IN ISSUE ON 12 OCTOBER 2026':
    raise ValueError('Wrong official valuation date')
official = {}
kind, bracket = None, None
for row in sheet.get_rows():
    v = [x.value for x in row]
    label = str(v[0])
    if label == 'Conventional Gilts': kind = 'Conventional'
    elif '3-month Indexation Lag' in label: kind = 'Index-linked 3 months'
    elif '8-month Indexation Lag' in label: kind = 'Index-linked 8 months'
    if label in ('Ultra-Short', 'Short', 'Medium', 'Long'): bracket = label
    if re.fullmatch(r'GB[A-Z0-9]{10}', str(v[1])):
        isin = v[1]
        if isin in official: raise ValueError('Duplicate official ISIN')
        official[isin] = dict(kind=kind, redemption=xlrd.xldate_as_datetime(v[2], book.datemode).date().isoformat(),
                              nominal=Decimal(str(v[6])), uplifted=Decimal(str(v[8] if v[8] != '' else v[6])))
submitted = {e.attrib['ISIN_CODE']: e.attrib for e in ET.parse(raw / 'manual/dmo_D1A_gilts_in_issue_20261012.xml').getroot()}
if set(official) != set(submitted): raise ValueError('Official/transcribed ISIN sets differ')
errors = []
maximum = Decimal(0)
for isin, o in official.items():
    s = submitted[isin]
    for field, expected in [('kind', s['INSTRUMENT_TYPE'].strip()), ('redemption', s['REDEMPTION_DATE'][:10])]:
        if o[field] != expected: errors.append((isin, field, o[field], expected))
    for field, source in [('nominal', 'TOTAL_AMOUNT_IN_ISSUE'), ('uplifted', 'TOTAL_AMOUNT_INCLUDING_IL_UPLIFT')]:
        delta = abs(o[field] - Decimal(s[source]))
        maximum = max(maximum, delta)
        # 0.01 GBP tolerance accommodates Excel binary representation, not material rounding.
        if delta > Decimal('0.00000001'): errors.append((isin, field, str(delta)))
if errors: raise ValueError(json.dumps(errors))
print(json.dumps({'rows': len(official), 'date': '2026-10-12', 'checked': ['ISIN set','instrument type','redemption','nominal','uplifted'], 'max_amount_difference_GBP_million': str(maximum), 'status': 'pass'}))
