from fractions import Fraction as Q
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ddb.lp import Problem, Moment, bounds, evaluate, check_certificate, LPError
from ddb.pa import const, overlap_after, PA
from ddb.model import kernel, SCENARIOS
from ddb.experiments import kernel_recursive_annual, kernel_iai
from ddb.diagnostics import identification
import pytest


def test_actual_support_not_disclosed():
    # A=100 delta4 and B=50 delta0+50 delta8 have identical disclosed moments.
    from ddb.model import Ledger, Discloser
    led=Ledger({'conv':[(Q(4),Q(100))]},{'conv':Q(8)},'gross')
    d=Discloser(led)
    p=Problem(led.supports,kernel(SCENARIOS['all'],0,1,led.supports,'gross'),
              d.amount('total',{'conv':Q(1)})+d.mean('mean',{'conv':Q(1)}),grid=Q(1))
    r=identification(p)
    assert not r['identified']
    assert r['lower'].value==0 and r['upper'].value==Q(1,2)
    # A boundary mean does force support, but only through the feasible set.
    led.atoms['conv']=[(Q(8),Q(100))]
    p.moments=d.amount('total',{'conv':Q(1)})+d.mean('mean',{'conv':Q(1)})
    assert identification(p)['identified']


def test_recursive_kernel_matches_scalar_recurrence():
    support={'conv':Q(8)}
    y=Q(45,1000)
    for t in (Q(0),Q(1,3),Q(1),Q(9,4),Q(5),Q(8)):
        atoms={'conv':[(t,Q(100))]}
        debt=Q(0)
        for k in range(1,6):
            first=evaluate(kernel(SCENARIOS['all'],k-1,k,support,'gross'),atoms,support)
            new=(1+y)*debt+(1+y/2)*first
            v=evaluate(kernel_recursive_annual(SCENARIOS['all'],f'y{k}',y,support,'gross'),atoms,support)
            assert v==new-debt
            debt=new
        assert evaluate(kernel_recursive_annual(SCENARIOS['all'],'cum5',y,support,'gross'),atoms,support)==debt
        assert debt>=evaluate(kernel_iai(SCENARIOS['all'],'cum5',y,support,'gross'),atoms,support)


def test_bad_certificate_rejected():
    p=Problem({'x':Q(1)},{'x':const(1,0,1)},[Moment('mass',{'x':const(1,0,1)},Q(1),Q(1))],grid=Q(1))
    b=bounds(p)[0]
    with pytest.raises(LPError):
        check_certificate(p,b.sense,b.value+1,b.measure,b.dual)
