"""Number properties + Caesar/ROT13 cipher by voice. Offline."""
from __future__ import annotations

import re

from core.skill_registry import skill


@skill(
    name="number_properties",
    description="Is a number prime/even/odd + its factors (offline).",
    patterns=[
        "17 prime hai kya", "factors nikalo 24 ke", "even hai ya odd",
        "ye number prime hai", "48 ke factors batao", "prime check karo",
        "number properties batao", "sam ya visham",
    ],
    required_entities=[],
)
def number_properties(slots: dict) -> str:
    from core.number_props import properties
    out = properties(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Kaunsa number, sir? Jaise '17 prime hai kya' ya '24 ke "
                   "factors batao'.")


_CIPHER_CMD = {"rot13", "rot", "caesar", "cipher", "se", "encode", "decode",
               "karo", "kar", "do", "text", "me", "mein", "badlo", "shift",
               "wala", "ko", "is"}


@skill(
    name="caesar_cipher",
    description="Encode/decode text with ROT13 or a Caesar shift (offline).",
    patterns=[
        "rot13 karo hello", "caesar cipher se encode karo",
        "13 shift karo text", "cipher me badlo",
        "rot13 decode karo", "caesar cipher decode",
        "text ko cipher karo",
    ],
    required_entities=[],
)
def caesar_cipher(slots: dict) -> str:
    from core.number_props import cipher
    raw = slots.get("raw_text") or slots.get("text") or ""
    low = raw.lower()
    decode = "decode" in low
    # explicit shift number ("13 shift" / "shift 5"), else ROT13
    sm = re.search(r"(\d{1,2})\s*shift|shift\s*(\d{1,2})|rot\s*(\d{1,2})", low)
    shift = 13
    if sm:
        shift = int(next(g for g in sm.groups() if g))
    # strip command words + the shift number to leave the payload
    body = " ".join(
        t for t in raw.split()
        if t.lower().strip(":-?\"'") not in _CIPHER_CMD
        and not re.fullmatch(r"\d{1,2}", t)).strip(" :-?\"'")
    out = cipher(body, shift=shift, decode=decode)
    if not out:
        return ("Kya cipher karun, sir? Text do — jaise 'rot13 karo hello' "
                "ya '5 shift karo secret'.")
    return f"{out}  (ROT{shift}{', decoded' if decode else ''})"


@skill(
    name="combinations_permutations",
    description="nCr combinations or nPr permutations of n items taken r (offline).",
    patterns=[
        "5 me se 3 kitne tarike se chun sakte", "combinations nikaalo",
        "10 choose 2 kitna", "permutations calculate karo",
        "ncr npr batao", "kitne combinations banenge",
    ],
    required_entities=[],
)
def combinations_permutations(slots: dict) -> str:
    from core.number_props import combinations_permutations as _cp
    return _cp(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="quadratic_solver",
    description="Solve a quadratic equation ax^2 + bx + c = 0 for its roots (offline).",
    patterns=[
        "2x2 + 3x - 5 = 0 solve karo", "quadratic equation solve karo",
        "a=1 b=-3 c=2 roots", "quadratic ke roots nikaalo",
        "equation ki roots batao", "2 3 -5 quadratic roots",
    ],
    required_entities=[],
)
def quadratic_solver(slots: dict) -> str:
    from core.number_props import quadratic_solver as _qs
    return _qs(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="trig_calc",
    description="sin, cos or tan of an angle in degrees or radians (offline).",
    patterns=[
        "sin 30 kitna hota hai", "cos 60 nikaalo",
        "tan 45 ki value", "trigonometry value batao",
        "sine cosine tangent nikaalo", "sin 90 degree",
    ],
    required_entities=[],
)
def trig_calc(slots: dict) -> str:
    from core.number_props import trig_calc as _tc
    return _tc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="log_calc",
    description="Logarithm: log base 10, natural log (ln), or log to any base (offline).",
    patterns=[
        "log 100 kitna hota hai", "ln 5 nikaalo",
        "log 8 base 2 batao", "logarithm calculate karo",
        "natural log nikaalo", "log value kya hai",
    ],
    required_entities=[],
)
def log_calc(slots: dict) -> str:
    from core.number_props import log_calc as _lc
    return _lc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="sequence_calc",
    description="Arithmetic/geometric progression: nth term and sum of n terms (offline).",
    patterns=[
        "first 2 difference 3 10 terms ka sum", "arithmetic progression nikaalo",
        "gp ka nth term aur sum", "geometric sequence calculate karo",
        "ap ka sum nikaalo", "series ka nth term batao",
    ],
    required_entities=[],
)
def sequence_calc(slots: dict) -> str:
    from core.number_props import sequence_calc as _sq
    return _sq(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="fibonacci",
    description="Nth Fibonacci number or the first N Fibonacci numbers (offline).",
    patterns=[
        "10th fibonacci number kya hai", "fibonacci nikaalo",
        "first 8 fibonacci numbers", "fibonacci series batao",
        "nth fibonacci calculate karo", "fibonacci sequence do",
    ],
    required_entities=[],
)
def fibonacci(slots: dict) -> str:
    from core.number_props import fibonacci as _fib
    return _fib(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="variance_std",
    description="Variance and standard deviation (population + sample) of numbers (offline).",
    patterns=[
        "variance of 4 8 15 16 23", "standard deviation nikaalo",
        "in numbers ka variance", "std deviation calculate karo",
        "data ka variance batao", "sd nikaalo numbers ka",
    ],
    required_entities=[],
)
def variance_std(slots: dict) -> str:
    from core.number_props import variance_std as _vs
    return _vs(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="weighted_average",
    description="Weighted average from value-weight pairs (offline).",
    patterns=[
        "80 weight 3 90 weight 2 weighted average", "weighted average nikaalo",
        "marks aur credits se average", "weightage ke saath average",
        "gpa jaisa weighted mean", "weighted mean calculate karo",
    ],
    required_entities=[],
)
def weighted_average(slots: dict) -> str:
    from core.number_props import weighted_average as _wa
    return _wa(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="prime_list",
    description="List primes between two numbers, or the first N primes (offline).",
    patterns=[
        "10 aur 30 ke beech primes", "prime numbers list karo",
        "first 10 prime numbers", "kitne primes hain is range me",
        "primes between 1 and 50", "pehle 20 prime numbers",
    ],
    required_entities=[],
)
def prime_list(slots: dict) -> str:
    from core.number_props import prime_list as _pl
    return _pl(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="z_score",
    description="Standard score (z-score) from a value, mean and standard deviation (offline).",
    patterns=[
        "value 85 mean 70 std 10 z score", "z score nikaalo",
        "standard score calculate karo", "kitne std deviations door hai",
        "z value batao", "standardize karo value ko",
    ],
    required_entities=[],
)
def z_score(slots: dict) -> str:
    from core.number_props import z_score as _zs
    return _zs(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="percent_error",
    description="Percent error between a measured value and the actual value (offline).",
    patterns=[
        "measured 95 actual 100 percent error", "percent error nikaalo",
        "experimental value ka error", "kitna error hai measurement me",
        "percentage error batao", "measured vs actual error",
    ],
    required_entities=[],
)
def percent_error(slots: dict) -> str:
    from core.number_props import percent_error as _pe
    return _pe(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="scientific_notation",
    description="Convert a number to scientific notation or expand it back (offline).",
    patterns=[
        "123000 ko scientific notation me likho", "scientific notation banao",
        "1.23e5 ko normal number me", "standard form me convert karo",
        "bade number ko scientific me", "scientific se decimal nikaalo",
    ],
    required_entities=[],
)
def scientific_notation(slots: dict) -> str:
    from core.number_props import scientific_notation as _sn
    return _sn(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="proportion_solve",
    description="Solve a proportion a:b = c:x for the unknown value (offline).",
    patterns=[
        "2:3 = x:12 me x nikaalo", "proportion solve karo",
        "ratio se unknown nikaalo", "2 ratio 3 barabar x ratio 12",
        "cross multiply se x", "anupaat se value nikaalo",
    ],
    required_entities=[],
)
def proportion_solve(slots: dict) -> str:
    from core.number_props import proportion_solve as _ps
    return _ps(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="rounding_sigfig",
    description="Round a number to N decimal places or N significant figures (offline).",
    patterns=[
        "3.14159 ko 2 decimal tak round karo", "rounding karo",
        "3 significant figures tak round", "number round off karo",
        "decimal places tak round karo", "sig figs me round karo",
    ],
    required_entities=[],
)
def rounding_sigfig(slots: dict) -> str:
    from core.number_props import rounding_sigfig as _rs
    return _rs(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="modulo_calc",
    description="Remainder and quotient of one number divided by another (offline).",
    patterns=[
        "17 mod 5 kitna hota hai", "remainder nikaalo",
        "100 ko 7 se divide karne pe remainder", "modulo calculate karo",
        "23 mod 4 batao", "bacha hua remainder kya hai",
    ],
    required_entities=[],
)
def modulo_calc(slots: dict) -> str:
    from core.number_props import modulo_calc as _mc
    return _mc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="base_arithmetic",
    description="Add/subtract/multiply two numbers in binary, octal, hex or base-N (offline).",
    patterns=[
        "1010 + 110 binary add karo", "binary addition karo",
        "ff + 1 hex me", "octal numbers add karo",
        "do binary numbers ka sum", "base me arithmetic karo",
    ],
    required_entities=[],
)
def base_arithmetic(slots: dict) -> str:
    from core.number_props import base_arithmetic as _ba
    return _ba(slots.get("raw_text") or slots.get("text") or "")
