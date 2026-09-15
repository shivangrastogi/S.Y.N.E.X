"""JSON pretty/minify/validate + URL encode-decode + slugify. Stdlib, offline."""
from __future__ import annotations

import json
import re
from urllib.parse import quote, unquote
from typing import Optional


def json_format(text: str) -> Optional[str]:
    t = text or ""
    start = min([i for i in (t.find("{"), t.find("[")) if i >= 0], default=-1)
    if start < 0:
        return "JSON do — jaise 'json format karo {\"a\":1}'."
    end = max(t.rfind("}"), t.rfind("]"))
    if end <= start:
        return "JSON adhoora lag raha — poora object/array do."
    blob = t[start:end + 1]
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e.msg} (line {e.lineno}, col {e.colno})."
    compact = bool(re.search(r"\b(minify|compact|ek line|one line|small)\b",
                             t, re.IGNORECASE))
    if compact:
        out = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
        return f"Minified:\n{out}"
    out = json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False)
    return f"Valid JSON, formatted:\n{out}"


_URL_CMD = (r"\b(url|uri|encode|decode|karo|kar|do|me|mein|banao|nikaalo|"
            r"convert|this|the|link|percent)\b")


def _payload(text: str) -> str:
    q = re.search(r"[\"'](.+?)[\"']", text or "")
    if q:
        return q.group(1)
    p = re.sub(_URL_CMD, " ", text or "", flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", p).strip(" \"'")


def url_convert(text: str) -> Optional[str]:
    payload = _payload(text)
    if not payload:
        return "Kya URL-encode/decode karu? Jaise 'url encode karo hello world'."
    if re.search(r"\bdecode\b|\bwapas\b", text or "", re.IGNORECASE):
        return f"URL decoded: {unquote(payload)}"
    return f"URL encoded: {quote(payload, safe='')}"


def slugify(text: str) -> Optional[str]:
    p = re.sub(r"\b(slug|slugify|banao|bana do|karo|kar do|url slug|"
               r"iska|is ka|for|generate)\b", " ", text or "", flags=re.IGNORECASE)
    p = p.strip(" \"'")
    slug = re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-")
    if not slug:
        return "Kis title ka slug? Jaise 'slug banao My First Blog Post!'."
    return f"Slug: {slug}"


_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_PIN_RE = re.compile(r"^[1-9][0-9]{5}$")


def id_validate(text: str) -> Optional[str]:
    """Validate PAN / IFSC / PIN-code format (offline, format only)."""
    t = text or ""
    tl = t.lower()
    # candidate token: alnum run of plausible length, ignore common words
    toks = re.findall(r"[A-Za-z0-9]{5,15}", t)
    cmd = {"validate", "check", "karo", "format", "batao", "sahi", "hai",
           "valid", "number", "code", "pan", "ifsc", "pincode", "pin"}
    cands = [w for w in toks if w.lower() not in cmd]
    cand = max(cands, key=len).upper() if cands else None

    def _pan(c): return "PAN", bool(c and _PAN_RE.match(c))
    def _ifsc(c): return "IFSC", bool(c and _IFSC_RE.match(c))
    def _pin(c): return "PIN code", bool(c and _PIN_RE.match(c))

    if "pan" in tl:
        checks = [_pan]
    elif "ifsc" in tl:
        checks = [_ifsc]
    elif re.search(r"\bpin\b|pincode|postal", tl):
        checks = [_pin]
    else:
        checks = [_pan, _ifsc, _pin]
    if not cand:
        return ("Number/code batao — jaise 'ABCDE1234F PAN valid hai kya' ya "
                "'SBIN0001234 ifsc check'.")
    for fn in checks:
        name, ok = fn(cand)
        if ok:
            return f"'{cand}' ek valid {name} format hai."
    # not matched — report what was expected for the requested type
    exp = {"_pan": "PAN = 5 letters + 4 digits + 1 letter (ABCDE1234F)",
           "_ifsc": "IFSC = 4 letters + 0 + 6 alnum (SBIN0001234)",
           "_pin": "PIN = 6 digits, pehla non-zero (110001)"}
    which = checks[0].__name__
    hint = exp.get(which, "PAN/IFSC/PIN me se koi valid format nahi")
    return f"'{cand}' valid format nahi lag raha. {hint}."


def luhn_check(text: str) -> Optional[str]:
    """Validate a number by the Luhn checksum (cards, IMEI, etc.). Format only."""
    digits = re.sub(r"\D", "", text or "")
    if len(digits) < 2:
        return ("Number do (kam se kam 2 digits) — jaise "
                "'79927398713 luhn valid hai kya'.")
    total = 0
    for idx, ch in enumerate(reversed(digits)):
        d = int(ch)
        if idx % 2 == 1:        # every 2nd digit from the right
            d *= 2
            if d > 9:
                d -= 9
        total += d
    ok = total % 10 == 0
    if ok:
        return f"{digits} Luhn check PASS (valid checksum)."
    need = (10 - total % 10) % 10
    return (f"{digits} Luhn check FAIL (invalid checksum). "
            f"Aakhri digit {need} hota to pass hota.")
