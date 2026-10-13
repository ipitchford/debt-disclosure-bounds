"""Re-check every stored certificate without the LP solver or the basis computation.

For each record in results/certificates/*.jsonl.gz the programme is rebuilt from its specification
(src/ddb/specs.py) and lp.check_certificate verifies, in exact rational arithmetic, that the stored
extremal portfolio is feasible and attains the value, and that the stored dual multipliers are dual
feasible with the same objective value. The value is also matched against results/*.json.
"""
import gzip
import json
import sys
from fractions import Fraction as Q
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ddb.lp import check_certificate  # noqa: E402
from ddb.frozen import decode, identity as model_identity

with gzip.open(ROOT/'results/exact-models.json.gz', 'rt') as handle:
    snapshots = json.load(handle)
paths = sorted((ROOT / 'results/certificates').glob('*.jsonl.gz'))
if {p.name for p in paths} != set(snapshots['certificateInventory']):
    raise ValueError('Certificate file inventory mismatch')
if '--frozen' not in sys.argv:
    from ddb import specs


def f(s):
    n, d = s.split("/")
    return Q(int(n), int(d))


n = 0
KEYS = ('country', 'perimeter', 'set', 'scenario', 'window', 'variant', 'kernel', 'candidate')
def key(d):
    return tuple(d.get(k, {'variant': 'baseline', 'kernel': 'first'}.get(k)) for k in KEYS)

for path in sorted((ROOT / "results" / "certificates").glob("*.jsonl.gz")):
    results = json.loads((ROOT / 'results' / path.name.replace('.jsonl.gz', '.json')).read_text())
    index = {key(row): row for row in results}
    if len(index) != len(results):
        raise ValueError(f'Duplicate result identities: {path.name}')
    k = 0
    seen = set()
    with gzip.open(path, "rt") as fh:
        for line in fh:
            rec = json.loads(line)
            snapshot = snapshots['models'][model_identity(rec['spec'])]
            if snapshot['spec'] != rec['spec']:
                raise ValueError('Model specification mismatch')
            prob = decode(snapshot['problem']) if '--frozen' in sys.argv else specs.build(rec['spec'])
            meas = {}
            for c, t, s, w in rec["primal"]:
                meas.setdefault(c, []).append((f(t), s, f(w)))
            check_certificate(prob, rec["sense"], f(rec["value"]), meas, [(i, f(y)) for i, y in rec["dual"]])
            row = index[key(rec['spec'])]
            field = ('worst_width_exact' if rec['spec'].get('mode') == 'coupled'
                     else 'lo_exact' if rec['sense'] == 'min' else 'hi_exact')
            identity = (key(rec['spec']), field)
            if identity in seen:
                raise ValueError(f'Duplicate certificate: {path.name}')
            seen.add(identity)
            if Q(rec['value']) != Q(row[field]):
                raise ValueError(f'Certificate/result mismatch: {path.name}: {field}')
            k += 1
    expected = {(key(row), field) for row in results
                for field in ('lo_exact', 'hi_exact', 'worst_width_exact') if field in row}
    if seen != expected:
        raise ValueError(f'Incomplete certificate coverage: {path.name}')
    if k != snapshots['certificateInventory'][path.name]:
        raise ValueError(f'Certificate count mismatch: {path.name}')
    print(f"{path.name}: {k} certificates verified", flush=True)
    n += k
if n != 4576:
    raise ValueError('Expected exactly 4576 certificates')
print(f"all {n} certificates verified and linked exactly to results")
print('Model source: ' + ('shipped exact snapshots (not source-data reproduction)' if '--frozen' in sys.argv else 'source-data rebuild'))
