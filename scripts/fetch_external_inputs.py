"""Obtain the required historical APF input from its source; fail on vintage drift."""
from pathlib import Path
import hashlib
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
url='https://www.bankofengland.co.uk/-/media/boe/files/markets/asset-purchase-facility/table-for-website.xlsx'
target=ROOT/'data/raw/boe_table-for-website.xlsx'
expected='f30e048d851762afe8bf466516992572cde7d00dda45b03cff2f9d2c68a87aef'
if target.exists():
    data=target.read_bytes()
else:
    request=urllib.request.Request(url,headers={'User-Agent':'EvidencePressResearch/1.0 (+https://evidencepress.org; ian-8516@agentmail.to)'})
    with urllib.request.urlopen(request,timeout=60) as response: data=response.read()
if hashlib.sha256(data).hexdigest()!=expected:
    raise SystemExit('Source vintage/hash mismatch; no file written. Obtain the exact historical source separately; offline frozen-model checking remains available.')
if not target.exists():
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as f: f.write(data)
print('Hash-matched APF source input present. Source terms still apply; this is not redistribution permission.')
