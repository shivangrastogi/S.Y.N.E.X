"""Fractions — decimal<->fraction convert + fraction arithmetic. Offline."""
from __future__ import annotations

import re
from fractions import Fraction
from typing import Optional


def _fmt_frac(f: Fraction) -> str:
    if f.denominator == 1:
        return str(f.numerator)
    return f"{f.numerator}/{f.denominator}"


def fraction_convert(text: str) -> Optional[str]:
    """Decimal->fraction, percent->fraction, or fraction->decimal."""
    t = (text or "").lower()
    frac = re.search(r"(-?\d+)\s*/\s*(\d+)", t)
    pct = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:%|percent)", t)
    dec = re.search(r"-?\d+\.\d+", t)
    to_dec = bool(re.search(r"\b(decimal|dashamlav|as decimal|to decimal)\b", t))

    if frac and to_dec:
        f = Fraction(int(frac.group(1)), int(frac.group(2)))
        return f"{_fmt_frac(f)} = {float(f):.6g} (decimal)."
    if pct:
        f = Fraction(pct.group(1)).limit_denominator(100000) / 100
        return f"{pct.group(1)}% = {_fmt_frac(f)} (fraction)."
    if dec:
        f = Fraction(dec.group(0)).limit_denominator(100000)
        return f"{dec.group(0)} = {_fmt_frac(f)} (fraction)."
    if frac:
        f = Fraction(int(frac.group(1)), int(frac.group(2)))
        simp = _fmt_frac(f)
        note = " (already simplest)" if simp == f"{frac.group(1)}/{frac.group(2)}" else ""
        return f"{frac.group(1)}/{frac.group(2)} = {simp}{note}; decimal {float(f):.6g}."
    return ("Number ya fraction do — jaise '0.75 as fraction' ya "
            "'3/4 as decimal' ya '25%'.")


def fraction_math(text: str) -> Optional[str]:
    """Add/subtract/multiply/divide two fractions. '1/2 + 1/3'."""
    t = (text or "").lower().replace("÷", "/").replace("×", "*")
    t = re.sub(r"\bdivid(?:e|ed)(?:\s+by)?\b", " / ", t)
    # group 1 greedily consumes a fraction's own slash, so a leftover '/' is
    # the division operator between the two fractions.
    m = re.search(r"(-?\d+(?:\s*/\s*\d+)?)\s*([+\-*x/])\s*(-?\d+(?:\s*/\s*\d+)?)", t)
    if not m:
        return ("Do fractions aur operator do — jaise '1/2 + 1/3' — main "
                "answer fraction me bata dunga.")
    def _pf(s):
        s = s.replace(" ", "")
        return Fraction(s)
    try:
        a = _pf(m.group(1))
        b = _pf(m.group(3))
    except (ValueError, ZeroDivisionError):
        return "Fractions samajh nahi aaye — jaise '1/2 + 1/3' do."
    op = m.group(2)
    if op == "+":
        res = a + b
    elif op == "-":
        res = a - b
    elif op in ("*", "x"):
        res = a * b
    else:                                 # division
        if b == 0:
            return "Zero se divide nahi kar sakte."
        res = a / b
    op_disp = "x" if op == "x" else op
    return (f"{_fmt_frac(a)} {op_disp} {_fmt_frac(b)} = {_fmt_frac(res)} "
            f"(= {float(res):.6g}).")


def mixed_number(text: str) -> Optional[str]:
    """Improper fraction <-> mixed number. '7/3 as mixed' / '2 1/3 as improper'."""
    t = (text or "").lower()
    mixed = re.search(r"(-?\d+)\s+(\d+)\s*/\s*(\d+)", t)
    if mixed:                       # whole + fraction -> improper
        w, n, d = int(mixed.group(1)), int(mixed.group(2)), int(mixed.group(3))
        if d == 0:
            return "Denominator zero nahi ho sakta."
        sign = -1 if w < 0 else 1
        num = abs(w) * d + n
        f = Fraction(sign * num, d)
        return f"{w} {n}/{d} = {_fmt_frac(f)} (improper fraction)."
    frac = re.search(r"(-?\d+)\s*/\s*(\d+)", t)
    if frac:                        # improper -> mixed
        n, d = int(frac.group(1)), int(frac.group(2))
        if d == 0:
            return "Denominator zero nahi ho sakta."
        f = Fraction(n, d)
        whole = int(f)
        rem = abs(f - whole)
        if rem == 0:
            return f"{n}/{d} = {whole} (whole number)."
        if whole == 0:
            return f"{n}/{d} = {_fmt_frac(f)} (already proper, no whole part)."
        return f"{n}/{d} = {whole} {rem.numerator}/{rem.denominator} (mixed number)."
    return ("Fraction do — jaise '7/3 as mixed' ya '2 1/3 as improper'.")
