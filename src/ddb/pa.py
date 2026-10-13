"""Piecewise-affine functions on [0, TMAX] with exact rational arithmetic.

A PA is a list of cells (a, b, alpha, beta) meaning f(t) = alpha + beta*t for a <= t < b; the cell
whose right end equals the support maximum is closed on the right. Outside all cells f = 0.

Support points carry a side: (e, "L") is the limit from the left of e (it belongs to the cell that
ends at e); (e, "R") belongs to the cell that starts at e. An actual maturity t lying exactly on an
edge is evaluated with side "R" (cells are left-closed). The single exception is a point at the
right end of the support, which is evaluated with side "L".
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as Q
from typing import Iterable

Cell = tuple[Q, Q, Q, Q]


def q(x) -> Q:
    """Exact rational from int/Fraction/float (floats are taken at their exact binary value)."""
    if isinstance(x, Q):
        return x
    if isinstance(x, int):
        return Q(x)
    if isinstance(x, float):
        return Q(x)
    if isinstance(x, str):
        return Q(x)
    raise TypeError(type(x))


@dataclass(frozen=True)
class PA:
    cells: tuple[Cell, ...]

    @staticmethod
    def make(cells: Iterable[tuple]) -> "PA":
        out = []
        for a, b, al, be in cells:
            a, b, al, be = q(a), q(b), q(al), q(be)
            if b <= a:
                continue
            out.append((a, b, al, be))
        out.sort()
        for (a0, b0, *_), (a1, b1, *_) in zip(out, out[1:]):
            if a1 < b0:
                raise ValueError("overlapping PA cells")
        return PA(tuple(out))

    def edges(self) -> set[Q]:
        s: set[Q] = set()
        for a, b, _, _ in self.cells:
            s.add(a)
            s.add(b)
        return s

    def at(self, t: Q, side: str = "R") -> Q:
        for a, b, al, be in self.cells:
            if side == "R" and a <= t < b:
                return al + be * t
            if side == "L" and a < t <= b:
                return al + be * t
        return Q(0)

    def scale(self, c) -> "PA":
        c = q(c)
        return PA(tuple((a, b, al * c, be * c) for a, b, al, be in self.cells))

    def __add__(self, other: "PA") -> "PA":
        """Pointwise sum, refining cells on the union of edges."""
        es = sorted(self.edges() | other.edges())
        cells = []
        for a, b in zip(es, es[1:]):
            mid = (a + b) / 2
            f = [c for c in self.cells if c[0] <= mid < c[1]]
            g = [c for c in other.cells if c[0] <= mid < c[1]]
            al = sum((c[2] for c in f), Q(0)) + sum((c[2] for c in g), Q(0))
            be = sum((c[3] for c in f), Q(0)) + sum((c[3] for c in g), Q(0))
            if f or g:
                cells.append((a, b, al, be))
        return PA(tuple(cells))


def const(c, lo, hi) -> PA:
    return PA.make([(lo, hi, c, 0)])


def indicator(a, b) -> PA:
    return PA.make([(a, b, 1, 0)])


def affine_on(a, b, alpha, beta) -> PA:
    return PA.make([(a, b, alpha, beta)])


def overlap_after(a, b, tmax) -> PA:
    """|[a,b) ∩ [t, inf)| as a function of t on [0, tmax]: the window time after refixing at t."""
    a, b, tmax = q(a), q(b), q(tmax)
    return PA.make([(0, min(a, tmax), b - a, 0), (a, min(b, tmax), b, -1)])


def overlap_before(a, b, tmax) -> PA:
    """|[a,b) ∩ [0, t)| as a function of t on [0, tmax]: the window time before t."""
    a, b, tmax = q(a), q(b), q(tmax)
    return PA.make([(a, min(b, tmax), -a, 1), (b, tmax, b - a, 0)])
