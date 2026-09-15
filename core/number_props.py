"""Number properties + Caesar/ROT13 cipher. Pure stdlib, offline."""
from __future__ import annotations

import re
from typing import Optional


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def _factors(n: int) -> list[int]:
    n = abs(n)
    fs = set()
    i = 1
    while i * i <= n:
        if n % i == 0:
            fs.add(i)
            fs.add(n // i)
        i += 1
    return sorted(fs)


def _prime_factorisation(n: int) -> list[int]:
    n = abs(n)
    out = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            out.append(d)
            n //= d
        d += 1 if d == 2 else 2
    if n > 1:
        out.append(n)
    return out


# Above this, trial-division primality/factorisation is too slow to run
# synchronously (a 200-digit garbage number would hang the assistant).
_MAX_ANALYSABLE = 10 ** 15


def properties(text: str) -> Optional[str]:
    m = re.search(r"-?\d+", text or "")
    if not m:
        return None
    n = int(m.group(0))
    if abs(n) > _MAX_ANALYSABLE:
        return (f"{'even' if n % 2 == 0 else 'odd'} hai, par itna bada number "
                "prime/factor check ke liye bahut bada hai, sir.")
    facts = ["even" if n % 2 == 0 else "odd"]
    if n >= 2:
        if _is_prime(n):
            facts.append("prime")
        else:
            facts.append("not prime")
            facts.append("prime factors " + " x ".join(
                map(str, _prime_factorisation(n))))
        fs = _factors(n)
        if 1 < len(fs) <= 20:
            facts.append(f"{len(fs)} divisors: " + ", ".join(map(str, fs)))
        elif len(fs) > 20:
            facts.append(f"{len(fs)} divisors")
    return f"{n}: " + " · ".join(facts) + "."


# ── Caesar / ROT13 ───────────────────────────────────────────────────── #

def caesar(text: str, shift: int) -> str:
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
        elif "A" <= ch <= "Z":
            out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
        else:
            out.append(ch)
    return "".join(out)


def cipher(text: str, shift: int = 13, decode: bool = False) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None
    return caesar(text, -shift if decode else shift)


# ── GCD / LCM / ratio ────────────────────────────────────────────────── #

import math as _math


def _nums(text: str, cap: int = 10 ** 12) -> list[int]:
    out = []
    for tok in re.findall(r"\d+", text or ""):
        v = int(tok)
        if v <= cap:
            out.append(v)
    return out


def gcd_lcm(text: str) -> Optional[str]:
    ns = _nums(text)
    if len(ns) < 2:
        return None
    ns = ns[:6]                      # cap operands so lcm can't explode
    g = ns[0]
    for x in ns[1:]:
        g = _math.gcd(g, x)
    try:
        l = ns[0]
        for x in ns[1:]:
            l = l * x // _math.gcd(l, x) if _math.gcd(l, x) else 0
            if l > 10 ** 18:
                l = None
                break
    except Exception:
        l = None
    nums_str = ", ".join(map(str, ns))
    lcm_str = str(l) if l is not None else "bahut bada"
    return f"{nums_str}: GCD/HCF = {g}, LCM = {lcm_str}."


def simplify_ratio(text: str) -> Optional[str]:
    ns = _nums(text)
    if len(ns) < 2:
        return None
    a, b = ns[0], ns[1]
    if a == 0 or b == 0:
        return "Ratio mein zero nahi chalta, sir."
    g = _math.gcd(a, b)
    sa, sb = a // g, b // g
    if (sa, sb) == (a, b):
        return f"{a}:{b} pehle se hi simplest form mein hai."
    return f"{a}:{b} = {sa}:{sb} (divided by {g})."


# ── stats + factorial/power ──────────────────────────────────────────── #

def _all_nums(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", text or "")]


def _fmtn(x: float) -> str:
    return str(int(x)) if abs(x - round(x)) < 1e-9 else f"{x:.4g}"


def stats(text: str) -> Optional[str]:
    ns = _all_nums(text)
    if len(ns) < 2:
        return None
    ns = ns[:200]
    total = sum(ns)
    mean = total / len(ns)
    sv = sorted(ns)
    mid = len(sv) // 2
    median = sv[mid] if len(sv) % 2 else (sv[mid - 1] + sv[mid]) / 2
    return (f"{len(ns)} numbers: sum {_fmtn(total)}, average {_fmtn(mean)}, "
            f"median {_fmtn(median)}, min {_fmtn(min(ns))}, max {_fmtn(max(ns))}.")


def factorial(text: str) -> Optional[str]:
    m = re.search(r"\d+", text or "")
    if not m:
        return None
    n = int(m.group(0))
    if n > 1000:
        return "1000 se bada factorial bahut hi bada hota hai, sir."
    return f"{n}! = {_math.factorial(n)}"


def power(text: str) -> Optional[str]:
    t = (text or "").lower()
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:power|\^|ki ghaat|ka ghaat|"
                  r"raise to|to the power)\s*(-?\d+(?:\.\d+)?)", t)
    if m:
        base, exp = float(m.group(1)), float(m.group(2))
    elif re.search(r"\bsquare\b|\bvarg\b", t):
        nm = re.search(r"-?\d+(?:\.\d+)?", t)
        if not nm:
            return None
        base, exp = float(nm.group(0)), 2
    elif re.search(r"\bcube\b|\bghan\b", t):
        nm = re.search(r"-?\d+(?:\.\d+)?", t)
        if not nm:
            return None
        base, exp = float(nm.group(0)), 3
    else:
        return None
    if abs(exp) > 300 or (abs(base) > 10 ** 6 and abs(exp) > 10):
        return "Itni badi power ka result sambhalna mushkil hai, sir."
    try:
        res = base ** exp
    except Exception:
        return None
    label = {2: "square", 3: "cube"}.get(exp, f"power {_fmtn(exp)}")
    return f"{_fmtn(base)} {label} = {_fmtn(res)}"


def combinations_permutations(text: str) -> "Optional[str]":
    """nCr (choose) or nPr (arrange). '5 me se 3 kitne tarike'."""
    import math as _m
    t = (text or "").lower()
    nums = [int(float(x)) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    if len(nums) < 2:
        return ("Do numbers do (n aur r) — jaise '5 choose 3' ya "
                "'5 me se 3' — main combinations/permutations bata dunga.")
    n, r = max(nums[0], nums[1]), min(nums[0], nums[1])
    if n > 1000:
        return "Numbers thode chhote rakho (n <= 1000)."
    is_perm = bool(re.search(r"\b(permut\w*|arrange\w*|npr|order|kramyog|vyavastha)\b", t))
    if is_perm:
        val = _m.perm(n, r)
        return f"{n}P{r} (permutations) = {val:,} (order matters)."
    val = _m.comb(n, r)
    return f"{n}C{r} (combinations) = {val:,} (order doesn't matter)."


def quadratic_solver(text: str) -> "Optional[str]":
    """Solve ax^2 + bx + c = 0. Accepts 'a=2 b=3 c=-5' or '2 3 -5'."""
    import math as _m
    t = (text or "").lower().replace("^2", "").replace("²", "")
    am = re.search(r"\ba\s*=\s*(-?\d+(?:\.\d+)?)", t)
    bm = re.search(r"\bb\s*=\s*(-?\d+(?:\.\d+)?)", t)
    cm = re.search(r"\bc\s*=\s*(-?\d+(?:\.\d+)?)", t)
    if am and bm and cm:
        a, b, c = float(am.group(1)), float(bm.group(1)), float(cm.group(1))
    else:
        nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", t)]
        if len(nums) < 3:
            return ("a, b, c do — jaise '2 3 -5' (2x^2 + 3x - 5 = 0) — "
                    "main roots nikaal dunga.")
        a, b, c = nums[0], nums[1], nums[2]
    if a == 0:
        return "'a' zero nahi ho sakta (warna quadratic nahi rahega)."
    disc = b * b - 4 * a * c
    head = f"{_fmtn(a)}x^2 + {_fmtn(b)}x + {_fmtn(c)} = 0 (D={_fmtn(disc)}): "
    if disc > 0:
        r1 = (-b + _m.sqrt(disc)) / (2 * a)
        r2 = (-b - _m.sqrt(disc)) / (2 * a)
        return head + f"do real roots x = {_fmtn(r1)} aur {_fmtn(r2)}."
    if disc == 0:
        r = -b / (2 * a)
        return head + f"ek repeated root x = {_fmtn(r)}."
    re_part = -b / (2 * a)
    im_part = _m.sqrt(-disc) / (2 * a)
    return head + (f"complex roots x = {_fmtn(re_part)} +/- {_fmtn(im_part)}i.")


def trig_calc(text: str) -> "Optional[str]":
    """sin/cos/tan of an angle (degrees by default, or radians)."""
    import math as _m
    t = (text or "").lower()
    m = re.search(r"\b(sine|sin|cosine|cos|tangent|tan)\b\s*(?:of|=|:)?\s*"
                  r"(-?\d+(?:\.\d+)?)", t)
    if not m:
        return ("Function aur angle do — jaise 'sin 30' ya 'cos 60' — "
                "main value bata dunga.")
    fn = m.group(1)
    ang = float(m.group(2))
    is_rad = bool(re.search(r"\b(radian|rad)\b", t))
    rad = ang if is_rad else _m.radians(ang)
    unit = "rad" if is_rad else "degrees"
    fn = {"sine": "sin", "cosine": "cos", "tangent": "tan"}.get(fn, fn)
    if fn == "tan" and abs(_m.cos(rad)) < 1e-12:
        return f"tan {_fmtn(ang)} {unit} undefined hai (cos zero)."
    val = {"sin": _m.sin, "cos": _m.cos, "tan": _m.tan}[fn](rad)
    if abs(val) < 1e-12:
        val = 0.0
    return f"{fn}({_fmtn(ang)} {unit}) = {val:.4f}."


def log_calc(text: str) -> "Optional[str]":
    """log base 10, natural log (ln), or log to a given base."""
    import math as _m
    t = (text or "").lower()
    bm = re.search(r"base\s*(\d+(?:\.\d+)?)", t)
    lnm = re.search(r"\bln\b\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)", t)
    logm = re.search(r"\blog\b\s*(?:of|=|:)?\s*(\d+(?:\.\d+)?)", t)
    if lnm:
        x = float(lnm.group(1))
        if x <= 0:
            return "Log sirf positive numbers ka hota hai."
        return f"ln({_fmtn(x)}) = {_m.log(x):.4f}."
    if logm:
        x = float(logm.group(1))
        if x <= 0:
            return "Log sirf positive numbers ka hota hai."
        if bm:
            base = float(bm.group(1))
            if base <= 0 or base == 1:
                return "Base positive aur 1 ke alawa hona chahiye."
            return f"log base {_fmtn(base)} of {_fmtn(x)} = {_m.log(x, base):.4f}."
        return f"log10({_fmtn(x)}) = {_m.log10(x):.4f}."
    return ("Number do — jaise 'log 100', 'ln 5' ya 'log 8 base 2' — "
            "main logarithm nikaal dunga.")


def sequence_calc(text: str) -> "Optional[str]":
    """Arithmetic or geometric progression: nth term + sum of n terms."""
    t = (text or "").lower()
    fm = re.search(r"(?:first|start|pehla|a\s*=)\s*(-?\d+(?:\.\d+)?)", t)
    nm = re.search(r"(\d+)\s*(?:terms?|term)", t)
    rm = re.search(r"(?:common ratio|ratio|gunnak|r\s*=)\s*(-?\d+(?:\.\d+)?)", t)
    dm = re.search(r"(?:common difference|difference|diff|antar|d\s*=)\s*(-?\d+(?:\.\d+)?)", t)
    is_geo = bool(rm or re.search(r"\b(geometric|gp|gunottar)\b", t))
    if not fm or not nm or (not rm and not dm):
        return ("First term, difference/ratio aur terms do — jaise "
                "'first 2 difference 3 10 terms' ya 'first 2 ratio 3 5 terms'.")
    a = float(fm.group(1))
    n = int(nm.group(1))
    if n < 1 or n > 10000:
        return "Terms 1 se 10000 ke beech do."
    if is_geo:
        r = float(rm.group(1)) if rm else 1.0
        nth = a * (r ** (n - 1))
        if abs(nth) > 1e300:
            return "Terms bahut bade ho gaye — chhoti values do."
        total = n * a if r == 1 else a * (r ** n - 1) / (r - 1)
        return (f"GP: first {_fmtn(a)}, ratio {_fmtn(r)}, {n} terms -> "
                f"nth term {_fmtn(nth)}, sum {_fmtn(total)}.")
    d = float(dm.group(1)) if dm else 0.0
    nth = a + (n - 1) * d
    total = n / 2 * (2 * a + (n - 1) * d)
    return (f"AP: first {_fmtn(a)}, difference {_fmtn(d)}, {n} terms -> "
            f"nth term {_fmtn(nth)}, sum {_fmtn(total)}.")


def fibonacci(text: str) -> "Optional[str]":
    """nth Fibonacci number, or the first N Fibonacci numbers."""
    t = (text or "").lower()
    m = re.search(r"(\d+)", t)
    if not m:
        return ("Kaunsa term? Jaise '10th fibonacci' ya 'first 8 fibonacci'.")
    n = int(m.group(1))
    if n > 1000:
        return "1000 tak hi Fibonacci nikaal sakta hoon, chhota number do."
    want_list = bool(re.search(r"\b(first|pehle|shuru|list|series|sequence)\b", t))
    if want_list:
        seq, x, y = [], 0, 1
        for _ in range(n):
            seq.append(x)
            x, y = y, x + y
        return f"First {n} Fibonacci: " + ", ".join(map(str, seq)) + "."
    # nth term (1-indexed: F1=0, F2=1, ... common convention F1=1? use 0-indexed friendly)
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return f"{n}th Fibonacci number = {a} (sequence 0,1,1,2,3,5...)."


def variance_std(text: str) -> "Optional[str]":
    """Variance + standard deviation (population and sample) of a dataset."""
    import math as _m
    ns = _all_nums(text)
    if len(ns) < 2:
        return ("Kam se kam 2 numbers do — jaise 'variance of 4 8 15 16 23' — "
                "main variance aur std deviation bata dunga.")
    ns = ns[:500]
    n = len(ns)
    mean = sum(ns) / n
    sq = sum((x - mean) ** 2 for x in ns)
    pop_var = sq / n
    samp_var = sq / (n - 1)
    return (f"{n} numbers (mean {_fmtn(mean)}): population variance "
            f"{_fmtn(pop_var)} (std {_fmtn(_m.sqrt(pop_var))}), sample variance "
            f"{_fmtn(samp_var)} (std {_fmtn(_m.sqrt(samp_var))}).")


def weighted_average(text: str) -> "Optional[str]":
    """Weighted mean from value-weight pairs. '80 weight 3, 90 weight 2'."""
    t = (text or "").lower()
    pairs = re.findall(r"(\d+(?:\.\d+)?)\s*(?:weight|weightage|w|x|\*|marks?|"
                       r"credit|credits)\s*(\d+(?:\.\d+)?)", t)
    if len(pairs) < 2:
        return ("Value-weight pairs do — jaise '80 weight 3, 90 weight 2' — "
                "main weighted average nikaal dunga.")
    num = den = 0.0
    for v, w in pairs:
        v, w = float(v), float(w)
        num += v * w
        den += w
    if den == 0:
        return "Total weight zero nahi ho sakta."
    wavg = num / den
    return (f"{len(pairs)} items: weighted average = {_fmtn(wavg)} "
            f"(total weight {_fmtn(den)}).")


def prime_list(text: str) -> "Optional[str]":
    """Primes between two numbers, or the first N primes."""
    t = (text or "").lower()
    nums = [int(float(x)) for x in re.findall(r"\d+(?:\.\d+)?", t)]
    if re.search(r"\b(first|pehle|shuru|top)\b", t) and nums:
        n = nums[0]
        if n > 500:
            return "500 tak hi primes list kar sakta hoon, chhota number do."
        out, cand = [], 2
        while len(out) < n:
            if _is_prime(cand):
                out.append(cand)
            cand += 1
        return f"First {n} primes: " + ", ".join(map(str, out)) + "."
    if len(nums) >= 2:
        lo, hi = min(nums[0], nums[1]), max(nums[0], nums[1])
        if hi - lo > 100000 or hi > 10 ** 7:
            return "Range thodi chhoti rakho (max 100000 span)."
        primes = [x for x in range(max(lo, 2), hi + 1) if _is_prime(x)]
        if not primes:
            return f"{lo} aur {hi} ke beech koi prime nahi hai."
        shown = primes if len(primes) <= 50 else primes[:50]
        tail = f" ... (+{len(primes)-50} more, total {len(primes)})" if len(primes) > 50 else ""
        return f"{lo}-{hi} ke beech {len(primes)} primes: " + ", ".join(map(str, shown)) + tail + "."
    return ("Range ya count do — jaise 'primes between 10 and 30' ya "
            "'first 10 primes'.")


def z_score(text: str) -> "Optional[str]":
    """Standard score: (value - mean) / std deviation."""
    t = (text or "").lower()
    vm = re.search(r"(?:value|score|x|raw)\s*(?:=|is)?\s*(-?\d+(?:\.\d+)?)", t)
    mm = re.search(r"(?:mean|average|mu|avg)\s*(?:=|is)?\s*(-?\d+(?:\.\d+)?)", t)
    sm = re.search(r"(?:std|standard deviation|sigma|sd|deviation)\s*(?:=|is)?\s*(-?\d+(?:\.\d+)?)", t)
    if vm and mm and sm:
        val, mean, std = float(vm.group(1)), float(mm.group(1)), float(sm.group(1))
    else:
        nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", t)]
        if len(nums) < 3:
            return ("Value, mean aur std do — jaise 'value 85 mean 70 std 10' "
                    "— main z-score bata dunga.")
        val, mean, std = nums[0], nums[1], nums[2]
    if std == 0:
        return "Standard deviation zero nahi ho sakta."
    z = (val - mean) / std
    where = ("mean se upar" if z > 0 else "mean se neeche" if z < 0 else "mean par")
    return (f"z-score = {_fmtn(z)} (value {_fmtn(val)}, {_fmtn(abs(z))} std "
            f"deviations {where}).")


def percent_error(text: str) -> "Optional[str]":
    """Percent error = |measured - actual| / |actual| * 100."""
    t = (text or "").lower()
    mm = re.search(r"(?:measured|experimental|observed|mapa|reading)\s*(?:=|is)?\s*(-?\d+(?:\.\d+)?)", t)
    am = re.search(r"(?:actual|true|expected|real|sahi|theoretical)\s*(?:=|is)?\s*(-?\d+(?:\.\d+)?)", t)
    if mm and am:
        measured, actual = float(mm.group(1)), float(am.group(1))
    else:
        nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", t)]
        if len(nums) < 2:
            return ("Measured aur actual value do — jaise 'measured 95 actual "
                    "100' — main percent error bata dunga.")
        measured, actual = nums[0], nums[1]
    if actual == 0:
        return "Actual value zero nahi ho sakta (error define nahi hoga)."
    err = abs(measured - actual) / abs(actual) * 100
    return (f"Percent error = {_fmtn(err)}% (measured {_fmtn(measured)}, "
            f"actual {_fmtn(actual)}, diff {_fmtn(abs(measured-actual))}).")


def scientific_notation(text: str) -> "Optional[str]":
    """Number <-> scientific notation."""
    import math as _m
    t = (text or "").lower()
    # expand form: has 'e' notation or 'x 10^'
    em = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:e|x\s*10\s*\^?|\*\s*10\s*\^?)\s*(-?\d+)", t)
    to_normal = bool(re.search(r"\b(normal|decimal|expand|standard form|todo)\b", t))
    if em and (to_normal or "e" in em.group(0) or "10" in em.group(0)):
        from decimal import Decimal
        mant = em.group(1)
        exp = int(em.group(2))
        if abs(exp) > 300:
            return "Exponent bahut bada hai — chhota rakho."
        val = Decimal(mant) * (Decimal(10) ** exp)   # exact digits, no float noise
        if val == val.to_integral_value():
            shown = format(val.to_integral_value(), "f")
        else:
            shown = format(val.normalize(), "f")
        return f"{mant} x 10^{exp} = {shown}."
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return ("Number do — jaise '123000 scientific' ya '1.23e5 normal' — "
                "main convert kar dunga.")
    n = float(m.group(0))
    if n == 0:
        return "0 = 0 x 10^0."
    exp = int(_m.floor(_m.log10(abs(n))))
    mant = n / (10 ** exp)
    return f"{_fmtn(n)} = {mant:.4g} x 10^{exp} (scientific notation)."


def proportion_solve(text: str) -> "Optional[str]":
    """Solve a proportion a:b = c:x for the unknown. '2:3 = x:12'."""
    t = (text or "").lower()
    m = re.search(r"(-?\d+(?:\.\d+)?|x|\?)\s*[:/]\s*(-?\d+(?:\.\d+)?|x|\?)\s*"
                  r"(?:=|::|equals?)\s*(-?\d+(?:\.\d+)?|x|\?)\s*[:/]\s*"
                  r"(-?\d+(?:\.\d+)?|x|\?)", t)
    if not m:
        return ("Proportion do — jaise '2:3 = x:12' — main unknown value "
                "nikaal dunga.")
    toks = [m.group(i) for i in range(1, 5)]
    unknown = [i for i, tk in enumerate(toks) if tk in ("x", "?")]
    if len(unknown) != 1:
        return "Exactly ek unknown (x) hona chahiye — jaise '2:3 = x:12'."
    vals = [None if tk in ("x", "?") else float(tk) for tk in toks]
    a, b, c, d = vals
    try:
        # a/b = c/d  ->  a*d = b*c
        if a is None:
            a = b * c / d
            res = a
        elif b is None:
            b = a * d / c
            res = b
        elif c is None:
            c = a * d / b
            res = c
        else:
            d = b * c / a
            res = d
    except ZeroDivisionError:
        return "Zero se divide ho raha hai — values check karo."
    return (f"{_fmtn(a)}:{_fmtn(b)} = {_fmtn(c)}:{_fmtn(d)} -> "
            f"x = {_fmtn(res)}.")


def rounding_sigfig(text: str) -> "Optional[str]":
    """Round a number to N decimal places or N significant figures."""
    import math as _m
    t = (text or "").lower()
    nm = re.search(r"-?\d+(?:\.\d+)?", t)
    if not nm:
        return ("Number aur precision do — jaise '3.14159 to 2 decimals' ya "
                "'12345 to 2 sig figs'.")
    x = float(nm.group(0))
    cm = re.search(r"(\d+)\s*(?:decimal|dashamlav|dp)", t)
    sm = re.search(r"(\d+)\s*(?:sig|significant|s\.?f)", t)
    if sm:
        n = int(sm.group(1))
        if x == 0:
            return "0 rounded to any sig figs = 0."
        if n < 1 or n > 15:
            return "Sig figs 1-15 ke beech do."
        d = n - int(_m.floor(_m.log10(abs(x)))) - 1
        r = round(x, d)
        r = int(r) if d <= 0 else r
        return f"{nm.group(0)} to {n} significant figures = {_fmtn(float(r))}."
    dp = int(cm.group(1)) if cm else 2
    if dp < 0 or dp > 15:
        return "Decimal places 0-15 ke beech do."
    r = round(x, dp)
    return f"{nm.group(0)} rounded to {dp} decimal places = {r:.{dp}f}."


def modulo_calc(text: str) -> "Optional[str]":
    """Remainder + quotient of a divided by b. '17 mod 5'."""
    t = (text or "").lower()
    m = re.search(r"(-?\d+)\s*(?:mod|modulo|%|remainder(?:\s*(?:of|when))?|"
                  r"divided by|/)\s*(-?\d+)", t)
    if not m:
        nums = [int(x) for x in re.findall(r"-?\d+", t)]
        if len(nums) < 2:
            return ("Do numbers do — jaise '17 mod 5' — main remainder aur "
                    "quotient bata dunga.")
        a, b = nums[0], nums[1]
    else:
        a, b = int(m.group(1)), int(m.group(2))
    if b == 0:
        return "Zero se divide/mod nahi ho sakta."
    q = a // b
    r = a % b
    return (f"{a} mod {b} = {r} (remainder). Quotient = {q}, "
            f"check: {b} x {q} + {r} = {a}.")


def base_arithmetic(text: str) -> "Optional[str]":
    """Add/subtract/multiply two numbers in binary/octal/hex/base-N."""
    t = (text or "").lower()
    if re.search(r"\bbinary\b|\bbase\s*2\b", t):
        base, bname = 2, "binary"
    elif re.search(r"\bhex\w*\b|\bbase\s*16\b", t):
        base, bname = 16, "hex"
    elif re.search(r"\boctal\b|\bbase\s*8\b", t):
        base, bname = 8, "octal"
    else:
        bm = re.search(r"base\s*(\d+)", t)
        base = int(bm.group(1)) if bm else None
        bname = f"base-{base}" if base else None
    if not base or not (2 <= base <= 36):
        return ("Base batao (binary/octal/hex ya 'base N') aur do numbers "
                "with +/-/* — jaise '1010 + 110 binary'.")
    digs = "0123456789abcdefghijklmnopqrstuvwxyz"[:base]
    pat = rf"([{digs}]+)\s*([+\-*])\s*([{digs}]+)"
    m = re.search(pat, t)
    if not m:
        return f"Do valid {bname} numbers aur operator do — jaise '1010 + 110 {bname}'."
    try:
        a = int(m.group(1), base)
        b = int(m.group(3), base)
    except ValueError:
        return f"Numbers {bname} ke valid digits me hone chahiye."
    op = m.group(2)
    res = a + b if op == "+" else a - b if op == "-" else a * b
    if res < 0:
        return f"Result negative ({res}) — {bname} me usually non-negative dikhate hain."
    def _to_base(n):
        if n == 0:
            return "0"
        out = ""
        while n:
            out = digs[n % base] + out
            n //= base
        return out
    return (f"{m.group(1)} {op} {m.group(3)} ({bname}) = {_to_base(res)} "
            f"({bname}) = {res} (decimal).")
