"""Everyday money math — discount, GST/tax, tip, EMI, simple interest.

Pure arithmetic, no rates fetched, no network. quick_calc already does
"X% of Y"; this covers the framed real-life calculations it doesn't.
"""
from __future__ import annotations

import re
from typing import Optional

# Two numbers where the % is usually written with a % sign or the word
# "percent/pct". We pull an amount (the bigger, rupee-ish number) and a
# rate (the %-tagged one) so word order doesn't matter.
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|pct|फीसदी|feesdi)")
_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)")


def _fmt(n: float) -> str:
    if abs(n - round(n)) < 1e-9:
        return f"{int(round(n)):,}"
    return f"{n:,.2f}"


def _amount_and_rate(text: str) -> Optional[tuple[float, float]]:
    """Return (amount, rate%) — rate is the %-tagged number, amount the
    other one. None if we can't find both."""
    pm = _PCT_RE.search(text)
    if not pm:
        return None
    rate = float(pm.group(1))
    # amount = first number that isn't the rate token
    nums = [float(x) for x in _NUM_RE.findall(text)]
    rate_val = rate
    others = [n for n in nums if abs(n - rate_val) > 1e-9]
    if not others:
        # e.g. "20% of 20" — degenerate but valid; use the rate as amount too
        others = [n for n in nums if n != rate_val] or [rate_val]
    # amount is the largest remaining number (rupee amounts dwarf a %)
    amount = max(others)
    return amount, rate


def discount(text: str) -> Optional[str]:
    ar = _amount_and_rate(text)
    if not ar:
        return None
    amount, rate = ar
    off = amount * rate / 100
    final = amount - off
    return (f"{_fmt(rate)}% off on {_fmt(amount)}: discount {_fmt(off)}, "
            f"final price {_fmt(final)}.")


def add_percent(text: str, label: str = "GST") -> Optional[str]:
    ar = _amount_and_rate(text)
    if not ar:
        return None
    amount, rate = ar
    tax = amount * rate / 100
    total = amount + tax
    return (f"{label} {_fmt(rate)}% on {_fmt(amount)}: {label} {_fmt(tax)}, "
            f"total {_fmt(total)}.")


def tip(text: str) -> Optional[str]:
    ar = _amount_and_rate(text)
    if not ar:
        return None
    amount, rate = ar
    t = amount * rate / 100
    return (f"{_fmt(rate)}% tip on {_fmt(amount)}: tip {_fmt(t)}, "
            f"total bill {_fmt(amount + t)}.")


def simple_interest(text: str) -> Optional[str]:
    """principal + rate% + time(years). '10000 pe 8% 3 saal'."""
    pm = _PCT_RE.search(text)
    if not pm:
        return None
    rate = float(pm.group(1))
    # years: a number followed by saal/year/yr; else the smallest non-rate num
    ym = re.search(r"(\d+(?:\.\d+)?)\s*(?:saal|year|yr|varsh)", text, re.I)
    nums = [float(x) for x in _NUM_RE.findall(text) if abs(float(x) - rate) > 1e-9]
    if ym:
        years = float(ym.group(1))
        principal = max(n for n in nums if abs(n - years) > 1e-9) if \
            len([n for n in nums if abs(n - years) > 1e-9]) else (
                max(nums) if nums else 0)
    else:
        if len(nums) < 2:
            return None
        principal, years = max(nums), min(nums)
    if principal <= 0 or years <= 0:
        return None
    si = principal * rate * years / 100
    return (f"Simple interest on {_fmt(principal)} @ {_fmt(rate)}% for "
            f"{_fmt(years)} saal: {_fmt(si)}. Total {_fmt(principal + si)}.")


def emi(text: str) -> Optional[str]:
    """principal + annual rate% + months. '500000 loan 12% 24 months'."""
    pm = _PCT_RE.search(text)
    if not pm:
        return None
    rate = float(pm.group(1))
    mm = re.search(r"(\d+(?:\.\d+)?)\s*(?:month|mahine|mahina|months|mah)",
                   text, re.I)
    ym = re.search(r"(\d+(?:\.\d+)?)\s*(?:saal|year|yr|varsh)", text, re.I)
    if mm:
        n = float(mm.group(1))
    elif ym:
        n = float(ym.group(1)) * 12
    else:
        return None
    nums = [float(x) for x in _NUM_RE.findall(text)
            if abs(float(x) - rate) > 1e-9 and abs(float(x) - n) > 1e-9
            and abs(float(x) - (n / 12)) > 1e-9]
    if not nums:
        return None
    principal = max(nums)
    r = rate / 12 / 100
    if r == 0:
        emi_val = principal / n
    else:
        emi_val = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)
    total = emi_val * n
    interest = total - principal
    return (f"Loan {_fmt(principal)} @ {_fmt(rate)}% for {int(n)} months: "
            f"EMI ~{_fmt(emi_val)}/month, total {_fmt(total)} "
            f"(interest {_fmt(interest)}).")


def percent_change(text: str) -> Optional[str]:
    """'100 se 150 kitna percent badha' → +50%. Needs an ordered pair
    'A se B' (from A to B)."""
    t = (text or "").lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:se|to|from|->|→)\s*(\d+(?:\.\d+)?)", t)
    if not m:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    if a == 0:
        return "Starting value zero hai — percent change define nahi hota."
    change = (b - a) / a * 100
    if abs(change) < 1e-9:
        return f"{_fmt(a)} se {_fmt(b)}: koi change nahi (0%)."
    direction = "badha" if change > 0 else "gira"
    return (f"{_fmt(a)} se {_fmt(b)}: {change:+.2f}% {direction} "
            f"(farq {_fmt(abs(b - a))}).")


# ── password strength (security) ─────────────────────────────────────── #

_COMMON = {"password", "123456", "qwerty", "admin", "welcome", "letmein",
           "iloveyou", "abc123", "111111", "000000", "shivang", "india"}


def password_strength(pw: str) -> str:
    if not pw:
        return "Koi password nahi mila check karne ke liye, sir."
    length = len(pw)
    classes = sum(bool(re.search(p, pw)) for p in
                  (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    pool = (26 * bool(re.search(r"[a-z]", pw)) + 26 * bool(re.search(r"[A-Z]", pw))
            + 10 * bool(re.search(r"\d", pw))
            + 32 * bool(re.search(r"[^A-Za-z0-9]", pw)))
    import math
    entropy = length * math.log2(pool) if pool else 0
    low = pw.lower()
    penalty = any(c in low for c in _COMMON) or re.search(r"(.)\1\1", pw)
    if penalty:
        verdict, tip = "KAMZOR", "common word/pattern hai — badlo."
    elif entropy < 40 or length < 8:
        verdict, tip = "WEAK", "kam se kam 12 chars + symbol + number rakho."
    elif entropy < 60:
        verdict, tip = "THEEK-THAAK", "ek symbol aur length add karo to strong."
    elif entropy < 80:
        verdict, tip = "STRONG", "achha hai."
    else:
        verdict, tip = "BAHUT STRONG", "solid password, sir."
    return (f"Password strength: {verdict} ({length} chars, {classes}/4 "
            f"character types, ~{entropy:.0f} bits entropy). {tip}")


# ── bill split ───────────────────────────────────────────────────────── #

def bill_split(text: str) -> Optional[str]:
    """'1200 ka bill 4 log me baato' (+ optional 'X% tip')."""
    t = (text or "").lower().replace(",", "")
    # people: "N log/logon/people/person/dost/ke beech"
    pm = re.search(r"(\d+)\s*(?:log|logon|logo|people|person|dost|jane|ke beech|"
                   r"me baato|mein baato|way)", t)
    tipm = _PCT_RE.search(t)
    nums = [float(x) for x in _NUM_RE.findall(t)]
    if not nums:
        return None
    people = int(pm.group(1)) if pm else 0
    tip_rate = float(tipm.group(1)) if tipm else 0.0
    # amount = largest number that isn't the people count or the tip rate
    excl = set()
    if people:
        excl.add(float(people))
    if tip_rate:
        excl.add(tip_rate)
    cands = [n for n in nums if n not in excl] or nums
    amount = max(cands)
    if not people or people < 1:
        return None
    total = amount * (1 + tip_rate / 100)
    per = total / people
    tip_note = f" (incl {_fmt(tip_rate)}% tip)" if tip_rate else ""
    return (f"{_fmt(amount)}{tip_note} ÷ {people} = {_fmt(per)} per person "
            f"(total {_fmt(total)}).")


def compound_interest(text: str) -> Optional[str]:
    """principal + rate% + time(years) + compounding frequency.
    '100000 pe 8% 5 saal quarterly compound'."""
    pm = _PCT_RE.search(text)
    if not pm:
        return None
    rate = float(pm.group(1))
    t = text.lower()
    ym = re.search(r"(\d+(?:\.\d+)?)\s*(?:saal|years?|yr|varsh)", t)
    nums = [float(x) for x in _NUM_RE.findall(text) if abs(float(x) - rate) > 1e-9]
    if ym:
        years = float(ym.group(1))
        rest = [n for n in nums if abs(n - years) > 1e-9]
        principal = max(rest) if rest else (max(nums) if nums else 0)
    else:
        if len(nums) < 2:
            return None
        principal, years = max(nums), min(nums)
    if principal <= 0 or years <= 0 or years > 1000:
        return None
    # compounding frequency
    freq, fname = 1, "yearly"
    if re.search(r"\b(quarter|quarterly|tri-?maasik)\b", t):
        freq, fname = 4, "quarterly"
    elif re.search(r"\b(month|monthly|maasik|mahin)", t):
        freq, fname = 12, "monthly"
    elif re.search(r"\b(half.?year|semi.?annual|ardh)", t):
        freq, fname = 2, "half-yearly"
    elif re.search(r"\b(dai?ly|roz)", t):
        freq, fname = 365, "daily"
    amount = principal * (1 + rate / 100 / freq) ** (freq * years)
    interest = amount - principal
    return (f"Compound interest on {_fmt(principal)} @ {_fmt(rate)}% for "
            f"{_fmt(years)} saal ({fname}): {_fmt(interest)}. "
            f"Maturity {_fmt(amount)}.")


def profit_loss(text: str) -> Optional[str]:
    """cost price + selling price -> profit/loss amount and %.
    'kharida 100 becha 150' / 'cost 100 sold 150'."""
    t = (text or "").lower()
    cp = sp = None
    cm = re.search(r"(?:cost|cp|kharida|khareeda|buy|bought|liya|purchase)\D{0,8}"
                   r"(\d+(?:\.\d+)?)", t)
    sm = re.search(r"(?:sold|sell|sp|becha|becha|sale|selling)\D{0,8}"
                   r"(\d+(?:\.\d+)?)", t)
    if cm:
        cp = float(cm.group(1))
    if sm:
        sp = float(sm.group(1))
    if cp is None or sp is None:
        nums = [float(x) for x in _NUM_RE.findall(text)]
        if len(nums) >= 2:
            # first number = cost, second = selling (natural spoken order)
            cp, sp = nums[0], nums[1]
    if cp is None or sp is None or cp <= 0:
        return ("Cost price aur selling price dono do — jaise "
                "'kharida 100 becha 150'.")
    diff = sp - cp
    pct = abs(diff) / cp * 100
    if diff > 0:
        return (f"Profit {_fmt(diff)} ({pct:.2f}%). "
                f"Cost {_fmt(cp)}, sold {_fmt(sp)}.")
    if diff < 0:
        return (f"Loss {_fmt(-diff)} ({pct:.2f}%). "
                f"Cost {_fmt(cp)}, sold {_fmt(sp)}.")
    return f"No profit no loss — dono {_fmt(cp)} par barabar."


def discount_stack(text: str) -> Optional[str]:
    """Sequential/stacked discounts. '1000 pe 20% phir 10% off' ->
    effective discount and final price. Two discounts don't simply add up."""
    t = (text or "").lower()
    rates = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*(?:%|percent|pct)", t)]
    if len(rates) < 2:
        return ("Do ya zyada discounts do — jaise '1000 pe 20% phir 10% off' — "
                "main effective discount bata dunga.")
    factor = 1.0
    for r in rates:
        factor *= (1 - r / 100)
    effective = (1 - factor) * 100
    # a base price = biggest number that isn't one of the rates
    nums = [float(x) for x in _NUM_RE.findall(text)]
    price_cands = [n for n in nums if n not in rates and n > max(rates)]
    chain = " then ".join(f"{_fmt(r)}%" for r in rates)
    if price_cands:
        price = max(price_cands)
        final = price * factor
        saved = price - final
        return (f"{chain} stacked = {effective:.2f}% effective (not "
                f"{_fmt(sum(rates))}%). {_fmt(price)} -> {_fmt(final)} "
                f"(save {_fmt(saved)}).")
    return (f"{chain} stacked = {effective:.2f}% effective discount "
            f"(simple add {_fmt(sum(rates))}% galat hota).")


# illustrative telescopic domestic slab (per unit) when no rate is given
_ELEC_SLABS = [(100, 4.0), (100, 5.5), (200, 7.0), (float("inf"), 8.0)]


def electricity_bill(text: str) -> Optional[str]:
    """units + optional rate -> bill. Flat if rate given, else slab estimate."""
    t = (text or "").lower()
    um = re.search(r"(\d+(?:\.\d+)?)\s*(?:units?|yunit|kwh|kilowatt)", t)
    units = float(um.group(1)) if um else None
    rm = re.search(r"(\d+(?:\.\d+)?)\s*(?:rupee|rupees|rs|₹|per unit|/unit)", t)
    rate = float(rm.group(1)) if rm else None
    if units is None:
        nums = [float(x) for x in _NUM_RE.findall(text)
                if rate is None or abs(float(x) - rate) > 1e-9]
        if nums:
            units = max(nums)
    if not units or units <= 0:
        return ("Kitne units? Jaise '350 units' ya '350 units 8 rupee' — "
                "main bill nikaal dunga.")
    if rate is not None:
        amt = units * rate
        return (f"{_fmt(units)} units @ {_fmt(rate)}/unit = {_fmt(amt)}. "
                "(Fixed charge/tax alag lag sakte hain.)")
    left = units
    total = 0.0
    for cap, r in _ELEC_SLABS:
        take = min(left, cap)
        total += take * r
        left -= take
        if left <= 0:
            break
    return (f"{_fmt(units)} units ka approx bill ~{_fmt(total)} "
            "(illustrative slab 4/5.5/7/8 per unit). "
            "Apne state ka rate do to exact ho jayega.")


def overtime_pay(text: str) -> Optional[str]:
    """overtime hours x hourly rate x multiplier (default 1.5x)."""
    t = (text or "").lower()
    hm = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|ghante|ghanta|h\b)", t)
    rm = re.search(r"(\d+(?:\.\d+)?)\s*(?:rupee|rupees|rs|₹)?\s*(?:per hour|/\s*h(?:r|our)?|per ghanta|prati ghanta|hourly)", t)
    # multiplier
    mult, mname = 1.5, "1.5x"
    if re.search(r"\b(2x|double|do\s*guna|dugna|twice)\b", t):
        mult, mname = 2.0, "2x"
    elif re.search(r"\b(1\.5x|dedh\s*guna|one and half)\b", t):
        mult, mname = 1.5, "1.5x"
    elif re.search(r"\b(3x|triple|teen\s*guna)\b", t):
        mult, mname = 3.0, "3x"
    hours = float(hm.group(1)) if hm else None
    rate = float(rm.group(1)) if rm else None
    if rate is None:
        # fall back: two plain numbers = hours, rate
        nums = [float(x) for x in _NUM_RE.findall(text)]
        nums = [n for n in nums if n not in (1.5, 2, 3)]
        if hours is not None:
            nums = [n for n in nums if abs(n - hours) > 1e-9]
            rate = max(nums) if nums else None
        elif len(nums) >= 2:
            hours, rate = min(nums), max(nums)
    if not hours or not rate or hours <= 0 or rate <= 0:
        return ("Overtime hours aur hourly rate do — jaise '8 hours 200 per "
                "hour 1.5x' — main overtime pay bata dunga.")
    pay = hours * rate * mult
    base = hours * rate
    return (f"{_fmt(hours)} hrs @ {_fmt(rate)}/hr x {mname} = {_fmt(pay)} "
            f"overtime pay (normal rate pe {_fmt(base)} hota).")


def _amount_with_scale(text: str, exclude=()):
    """Largest rupee amount, expanding lakh/crore words. Excludes given values."""
    best = None
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(lakh|lac|crore|cr|thousand|k|hazaar)?", text):
        v = float(m.group(1))
        unit = (m.group(2) or "").lower()
        v *= {"lakh": 1e5, "lac": 1e5, "crore": 1e7, "cr": 1e7,
              "thousand": 1e3, "k": 1e3, "hazaar": 1e3}.get(unit, 1.0)
        if any(abs(v - e) < 1e-6 for e in exclude):
            continue
        if best is None or v > best:
            best = v
    return best


def sip_calculator(text: str) -> Optional[str]:
    """Monthly SIP -> maturity. FV = P*((1+i)^n - 1)/i*(1+i)."""
    t = (text or "").lower()
    pm = _PCT_RE.search(text)
    if not pm:
        return None
    rate = float(pm.group(1))
    ym = re.search(r"(\d+(?:\.\d+)?)\s*(?:saal|years?|yr|varsh)", t)
    if not ym:
        return ("SIP ke liye monthly amount, return % aur saal do — jaise "
                "'5000 monthly 12% 10 saal'.")
    years = float(ym.group(1))
    mm = re.search(r"(\d+(?:\.\d+)?)\s*(?:per month|monthly|/month|maheena|"
                   r"pratimah|sip|mahine)", t)
    monthly = float(mm.group(1)) if mm else _amount_with_scale(
        text, exclude=(rate, years))
    if not monthly or monthly <= 0 or years <= 0:
        return "Monthly amount aur saal sahi do — jaise '5000 monthly 12% 10 saal'."
    i = rate / 100 / 12
    n = int(round(years * 12))
    if i == 0:
        fv = monthly * n
    else:
        fv = monthly * (((1 + i) ** n - 1) / i) * (1 + i)
    invested = monthly * n
    gain = fv - invested
    return (f"{_fmt(monthly)}/month SIP @ {_fmt(rate)}% for {_fmt(years)} saal: "
            f"maturity ~{_fmt(fv)}. Invested {_fmt(invested)}, gain {_fmt(gain)}.")


def savings_goal(text: str) -> Optional[str]:
    """Monthly saving needed to reach a target in N years (optional return %)."""
    t = (text or "").lower()
    ym = re.search(r"(\d+(?:\.\d+)?)\s*(?:saal|years?|yr|varsh|month|mahine)", t)
    if not ym:
        return ("Target amount aur time do — jaise '5 lakh 2 saal me' — main "
                "monthly saving bata dunga.")
    yval = float(ym.group(1))
    months = yval if re.search(r"month|mahine", ym.group(0)) else yval * 12
    pm = _PCT_RE.search(text)
    rate = float(pm.group(1)) if pm else None
    target = _amount_with_scale(text, exclude=(yval,) + ((rate,) if rate else ()))
    if not target or target <= 0 or months <= 0:
        return "Target aur time sahi do — jaise '500000 3 saal me'."
    n = int(round(months))
    if rate:
        i = rate / 100 / 12
        monthly = target / ((((1 + i) ** n - 1) / i) * (1 + i)) if i else target / n
        return (f"{_fmt(target)} in {_fmt(months)} months @ {_fmt(rate)}%: "
                f"~{_fmt(monthly)}/month bachao.")
    monthly = target / n
    return (f"{_fmt(target)} in {_fmt(months)} months: ~{_fmt(monthly)}/month "
            "bachao (bina interest ke). Return % do to kam ho jayega.")


def inflation_adjust(text: str) -> Optional[str]:
    """Future cost + today's-worth of an amount after N years of inflation."""
    t = (text or "").lower()
    pm = _PCT_RE.search(text)
    rate = float(pm.group(1)) if pm else 6.0     # default ~6% (India-ish)
    ym = re.search(r"(\d+(?:\.\d+)?)\s*(?:saal|years?|yr|varsh)", t)
    if not ym:
        return ("Amount aur saal do — jaise '1 lakh 10 saal 6% inflation' — "
                "main future value bata dunga.")
    years = float(ym.group(1))
    amount = _amount_with_scale(text, exclude=(rate, years))
    if not amount or amount <= 0 or years <= 0:
        return "Amount aur saal sahi do — jaise '100000 10 saal 6% inflation'."
    future_cost = amount * (1 + rate / 100) ** years
    worth_today = amount / (1 + rate / 100) ** years
    rate_note = "" if pm else " (maana 6%)"
    return (f"{_fmt(rate)}% inflation{rate_note} pe {_fmt(years)} saal baad: "
            f"aaj ki {_fmt(amount)} ki cheez ~{_fmt(future_cost)} ki hogi; "
            f"aur aaj ke {_fmt(amount)} sirf ~{_fmt(worth_today)} ke barabar rahenge.")


def rule_of_72(text: str) -> Optional[str]:
    """Rule of 72: years to double at a rate, or the rate to double in N years."""
    t = (text or "").lower()
    pm = _PCT_RE.search(text)
    ym = re.search(r"(\d+(?:\.\d+)?)\s*(?:saal|years?|yr|varsh)", t)
    if pm and not ym:
        rate = float(pm.group(1))
        if rate <= 0:
            return "Rate positive honi chahiye."
        yrs = 72 / rate
        return (f"Rule of 72: {_fmt(rate)}% pe paisa ~{yrs:.1f} saal me double "
                "ho jata hai.")
    if ym and not pm:
        yrs = float(ym.group(1))
        if yrs <= 0:
            return "Saal positive hone chahiye."
        rate = 72 / yrs
        return (f"Rule of 72: {_fmt(yrs)} saal me double karne ke liye "
                f"~{rate:.1f}% return chahiye.")
    if pm and ym:
        rate = float(pm.group(1))
        yrs = 72 / rate if rate else 0
        return (f"Rule of 72: {_fmt(rate)}% pe ~{yrs:.1f} saal me double.")
    return ("Rate ya time do — jaise '8% pe kab double' ya '5 saal me double "
            "kaunsa rate'.")


def _scaled_amounts(text: str, exclude=()):
    """Amounts in text order, expanding lakh/crore/k. Excludes given values."""
    out = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(lakh|lac|crore|cr|thousand|k|hazaar)?", text):
        v = float(m.group(1))
        unit = (m.group(2) or "").lower()
        v *= {"lakh": 1e5, "lac": 1e5, "crore": 1e7, "cr": 1e7,
              "thousand": 1e3, "k": 1e3, "hazaar": 1e3}.get(unit, 1.0)
        if any(abs(v - e) < 1e-6 for e in exclude):
            continue
        out.append(v)
    return out


def cagr(text: str) -> Optional[str]:
    """Compound annual growth rate: (end/start)^(1/years) - 1."""
    t = (text or "").lower()
    ym = re.search(r"(\d+(?:\.\d+)?)\s*(?:saal|years?|yr|varsh)", t)
    if not ym:
        return ("Start value, end value aur saal do — jaise '1 lakh se 2 lakh "
                "5 saal' — main CAGR nikaal dunga.")
    years = float(ym.group(1))
    amts = _scaled_amounts(text, exclude=(years,))
    if len(amts) < 2 or years <= 0:
        return "Do amounts aur saal do — jaise '100000 se 200000 5 saal'."
    start, end = amts[0], amts[1]
    if start <= 0 or end <= 0:
        return "Amounts positive hone chahiye."
    cagr_v = ((end / start) ** (1 / years) - 1) * 100
    total = (end / start - 1) * 100
    return (f"{_fmt(start)} se {_fmt(end)} in {_fmt(years)} saal: CAGR "
            f"~{cagr_v:.2f}%/year (total return {total:.1f}%).")


def down_payment(text: str) -> Optional[str]:
    """Home price + down% -> down payment amount and loan amount."""
    t = (text or "").lower()
    pm = _PCT_RE.search(text)
    if not pm:
        return ("Price aur down payment % do — jaise '50 lakh ghar 20% down' "
                "— main down aur loan bata dunga.")
    pct = float(pm.group(1))
    amts = _scaled_amounts(text, exclude=(pct,))
    price = max(amts) if amts else None
    if not price or price <= 0 or not (0 < pct < 100):
        return "Price aur down % sahi do — jaise '5000000 20% down payment'."
    down = price * pct / 100
    loan = price - down
    return (f"{_fmt(price)} price, {_fmt(pct)}% down = {_fmt(down)} down "
            f"payment, {_fmt(loan)} loan lena padega.")


def break_even(text: str) -> Optional[str]:
    """Break-even units = fixed cost / (price - variable cost per unit).
    'fixed 50000 price 200 variable cost 120'."""
    t = (text or "").lower().replace(",", "")
    fm = re.search(r"fixed\s*(?:cost|cost hai|kharcha)?\s*(\d+(?:\.\d+)?)", t)
    pm = re.search(r"(?:price|selling|sell|sp|bech)\w*\s*(\d+(?:\.\d+)?)", t)
    vm = re.search(r"(?:variable|per unit|unit cost|banane|making|cost per)\s*"
                   r"(?:cost)?\s*(\d+(?:\.\d+)?)", t)
    if not (fm and pm and vm):
        return ("Fixed cost, selling price aur per-unit cost do — jaise "
                "'fixed 50000 price 200 variable cost 120'.")
    fixed, price, var = float(fm.group(1)), float(pm.group(1)), float(vm.group(1))
    margin = price - var
    if margin <= 0:
        return ("Price per-unit cost se zyada honi chahiye, warna break-even "
                "kabhi nahi aayega.")
    import math
    units = fixed / margin
    return (f"Break-even: {math.ceil(units)} units (exact {units:.1f}). "
            f"Har unit {_fmt(margin)} contribute karta hai; "
            f"revenue {_fmt(math.ceil(units) * price)}.")


def markup_margin(text: str) -> Optional[str]:
    """cost + markup% -> selling & margin, or cost + margin% -> selling & markup."""
    t = (text or "").lower().replace(",", "")
    pm = _PCT_RE.search(text)
    cm = re.search(r"(?:cost|cp|kharida|buy|lagat)\w*\s*(\d+(?:\.\d+)?)", t)
    if not pm or not cm:
        return ("Cost aur markup/margin % do — jaise 'cost 100 markup 25%' "
                "ya 'cost 100 margin 20%'.")
    rate = float(pm.group(1))
    cost = float(cm.group(1))
    if cost <= 0:
        return "Cost positive honi chahiye."
    is_margin = bool(re.search(r"\bmargin\b", t))
    if is_margin:
        if rate >= 100:
            return "Margin 100% se kam honi chahiye."
        sell = cost / (1 - rate / 100)
        markup = (sell - cost) / cost * 100
        return (f"Cost {_fmt(cost)}, {_fmt(rate)}% margin: selling price "
                f"{_fmt(sell)} (markup {markup:.1f}%).")
    sell = cost * (1 + rate / 100)
    margin = (sell - cost) / sell * 100
    return (f"Cost {_fmt(cost)}, {_fmt(rate)}% markup: selling price "
            f"{_fmt(sell)} (margin {margin:.1f}%).")


def gst_inclusive(text: str) -> Optional[str]:
    """Extract base price + tax from a GST-inclusive amount.
    '1180 me se 18% gst nikaalo' -> base 1000, gst 180."""
    ar = _amount_and_rate(text)
    if not ar:
        return ("Total (GST included) aur rate do — jaise '1180 me se 18% "
                "gst' — main base price aur tax alag kar dunga.")
    total, rate = ar
    if rate < 0 or total <= 0:
        return "Amount aur rate sahi do."
    base = total / (1 + rate / 100)
    tax = total - base
    return (f"{_fmt(total)} me {_fmt(rate)}% GST included hai: base price "
            f"{_fmt(base)} + GST {_fmt(tax)}. (CGST {_fmt(tax/2)} + SGST {_fmt(tax/2)}.)")


def appliance_power_cost(text: str) -> Optional[str]:
    """Electricity cost of an appliance: watts x hours x days / 1000 x rate.
    '1500 watt 8 hours daily 30 days 8 rupee'."""
    t = (text or "").lower().replace(",", "")
    wm = re.search(r"(\d+(?:\.\d+)?)\s*(?:watt|watts|w\b|kw\b)", t)
    if not wm:
        return ("Wattage aur daily hours do — jaise '1500 watt 8 hours' — "
                "main units aur bill bata dunga.")
    watts = float(wm.group(1))
    if re.search(r"\bkw\b", t):
        watts *= 1000
    hm = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|ghante|hr\b)", t)
    if not hm:
        return "Roz kitne ghante chalega? Jaise '1500 watt 8 hours daily'."
    hours = float(hm.group(1))
    dm = re.search(r"(\d+(?:\.\d+)?)\s*(?:days?|din)", t)
    days = float(dm.group(1)) if dm else 30.0
    rm = re.search(r"(\d+(?:\.\d+)?)\s*(?:rupee|rupees|rs|₹|/unit|per unit)", t)
    rate = float(rm.group(1)) if rm else None
    units = watts * hours * days / 1000
    period = f"{_fmt(days)} din" if dm else "mahine (30 din)"
    if rate is None:
        return (f"{_fmt(watts)}W, {_fmt(hours)} hr/day, {period}: "
                f"{_fmt(units)} units. Rate do to bill bhi bata dunga.")
    cost = units * rate
    return (f"{_fmt(watts)}W, {_fmt(hours)} hr/day, {period}: {_fmt(units)} "
            f"units @ {_fmt(rate)}/unit = {_fmt(cost)}.")
