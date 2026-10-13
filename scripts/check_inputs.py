"""Check required computation inputs; keep unused source hashes as provenance."""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[1]/'data'
required={'raw/manual/dmo_D1A_gilts_in_issue_20261012.xml',
          'raw/manual/dmo_tbill_issuance_and_stock_20261013.xls',
          'raw/manual/obr_efo_march2026_detailed_forecast_tables_debt_interest.xlsx',
          'raw/boe_table-for-website.xlsx','raw/us/mspd_table_3_market_20260930.json',
          'raw/dmo_official_gilts_20261012.xls'}
hashes=dict((line.split()[1],line.split()[0]) for line in (ROOT/'INPUTS.sha256').read_text().splitlines())
for name in sorted(required):
    p=ROOT/name
    if not p.is_file(): raise SystemExit('Missing '+name+'; see data/EXTERNAL_INPUTS.md')
    if hashlib.sha256(p.read_bytes()).hexdigest()!=hashes[name]: raise SystemExit('Input hash mismatch: '+name)
print('All six required computational source inputs match their recorded hashes.')
