"""Portable exact model snapshots; not a substitute for the source-to-model audit."""
import hashlib
import json
from fractions import Fraction as Q
from .lp import Problem, Moment, Coupling
from .pa import PA

def identity(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def encode(p):
    def terms(d):
        return {k: [[str(v) for v in cell] for cell in f.cells] for k, f in d.items()}
    return {'supports': {k:str(v) for k,v in p.supports.items()},
            'objective': terms(p.objective), 'grid': None if p.grid is None else str(p.grid),
            'moments': [{'name':m.name, 'terms':terms(m.terms),
                         'lo':None if m.lo is None else str(m.lo),
                         'hi':None if m.hi is None else str(m.hi)} for m in p.moments],
            'couplings':[{'name':c.name, 'weights':{k:str(v) for k,v in c.weights.items()}} for c in p.couplings]}

def decode(d):
    def terms(ts):
        return {k:PA.make(cells) for k,cells in ts.items()}
    return Problem({k:Q(v) for k,v in d['supports'].items()}, terms(d['objective']),
                   [Moment(m['name'],terms(m['terms']),None if m['lo'] is None else Q(m['lo']),
                           None if m['hi'] is None else Q(m['hi'])) for m in d['moments']],
                   [Coupling(c['name'],{k:Q(v) for k,v in c['weights'].items()}) for c in d['couplings']],
                   None if d['grid'] is None else Q(d['grid']))
