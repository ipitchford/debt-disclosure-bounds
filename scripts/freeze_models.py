"""Generate or check exact model snapshots against the source-based builder.

Requires the external source inputs. --check compares, without overwriting.
"""
import gzip
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ddb import specs
from ddb.frozen import encode, decode, identity

records={}
inventory={}
for path in sorted((ROOT/'results/certificates').glob('*.jsonl.gz')):
    count=0
    with gzip.open(path,'rt') as f:
        for line in f:
            r=json.loads(line); s=r['spec']; key=identity(s)
            if key not in records:
                p=specs.build(s); encoded=encode(p)
                if encode(decode(encoded)) != encoded:
                    raise ValueError('Model roundtrip failure')
                records[key]={'spec':s,'problem':encoded}
            count+=1
    inventory[path.name]=count
if sum(inventory.values()) != 4576:
    raise ValueError('Expected exactly 4576 endpoint certificates')
payload={'schema':'debt-disclosure-exact-models/v1','certificateInventory':inventory,'models':records}
target=ROOT/'results/exact-models.json.gz'
if '--check' in sys.argv:
    with gzip.open(target,'rt') as f:
        if json.load(f) != payload: raise ValueError('Source-to-model snapshot mismatch')
else:
    target.write_bytes(gzip.compress((json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n').encode(),mtime=0))
print(f'{len(records)} exact model snapshots; {sum(inventory.values())} certificates; source comparison passed')
