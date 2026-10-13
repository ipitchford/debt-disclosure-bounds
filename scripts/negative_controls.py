"""Failure-sensitive certificate mutations; works with Python assertions disabled."""
from fractions import Fraction as Q
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ddb.lp import Problem, Moment, Bound, check_certificate, LPError
from ddb.pa import const

p = Problem({'x':Q(1)}, {'x':const(1,0,1)}, [Moment('mass',{'x':const(1,0,1)},Q(1),Q(1))],grid=Q(1))
b = Bound(value=Q(1), measure={'x':[(Q(0),'R',Q(1))]}, certified=True, dual=[(0,Q(1))], sense='min')
check_certificate(p,b.sense,b.value,b.measure,b.dual)
bad = [
    ('wrong value', b.sense,b.value+1,b.measure,b.dual),
    ('missing primal', b.sense,b.value,{},b.dual),
    ('missing dual', b.sense,b.value,b.measure,[]),
    ('unknown sense','nonsense',b.value,b.measure,b.dual),
    ('duplicate dual',b.sense,b.value,b.measure,b.dual+b.dual),
    ('negative index',b.sense,b.value,b.measure,[(-1,Q(1))]),
]
for label,sense,value,measure,dual in bad:
    try: check_certificate(p,sense,value,measure,dual)
    except LPError: print('rejected:',label)
    else: raise RuntimeError('Accepted corrupted certificate: '+label)
print('All six semantic negative controls rejected; valid control accepted.')
