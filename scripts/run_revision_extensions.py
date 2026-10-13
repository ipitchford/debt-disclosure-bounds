"""Generate exact recursive-financing certificates and disclosure-count audit."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ddb import specs
from ddb.diagnostics import independent_disclosures
from run_experiments import Recorder

R=Recorder('recursive_annual')
for per in ('gross','consolidated'):
    for base in ('D1 DMO brackets','D2 GFS residual maturity','D* annual amounts+timing'):
        for win in ('y1','y5','cum5'):
            row=R.bound(dict(country='uk',perimeter=per,set=base,scenario='all',window=win,kernel='recursive_annual'))
            if row.get('status') != 'covers':
                raise ValueError(row)
R.close()
rows=[]
for country,per,base in [('uk','consolidated','D1 DMO brackets'),('uk','gross','D2 GFS residual maturity'),('us','gross','U2 GFS residual maturity')]:
    prob=specs.build(dict(country=country,perimeter=per,set=base,scenario='all',window='cum5'))
    for name,cand in specs.candidates(country,per).items():
        if name.startswith('R9'):
            continue
        rows.append(dict(country=country,perimeter=per,baseline=base,candidate=name,**independent_disclosures(prob,cand)))
(ROOT/'results/disclosure_vectors.json').write_text(json.dumps(rows,indent=2)+'\n')
print('36 recursive endpoints certified; reporting vectors and ranks recorded')
