"""Exact arithmetic on published APF account lines; not a fiscal forecasting model."""
from fractions import Fraction as Q

if 13304 + 134833 - 101372 - 25051 != 21714:
    raise ValueError('Cash-flow reconciliation failed')
roll = 656387 - 101372 + 24559 - 25051
if abs(roll - 554522) > 1:
    raise ValueError('Loan roll-forward exceeds reported rounding discrepancy')
if 21714 + 382080 + 150677 + 51 != 554522:
    raise ValueError('Balance sheet does not close')
# GBP million; principal rounded to GBP0.1bn, deposit to GBP1m.
lower = (Q(553200)-50-Q(21714)-Q(1,2))/100/1000
upper = (Q(553200)+50-Q(21714)+Q(1,2))/100/1000
if (lower, upper) != (Q('5.314355'), Q('5.315365')):
    raise ValueError('Frozen-balance rounding bounds failed')
print('Cash and balance sheet reconcile; loan roll-forward differs by GBP1m at published precision.')
print('Conditional frozen-balance net sensitivity: GBP',float(lower),float(upper),'billion per 1pp year.')
