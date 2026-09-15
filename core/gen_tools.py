"""Generators & digests — password, hash, UUID. Pure stdlib, offline.

A standalone assistant makes its own secrets: `secrets` for crypto-random
passwords, `hashlib` for digests, `uuid` for ids. No network, no services.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import string
import uuid
from typing import Optional

_AMBIG = "O0oIl1|`'\""  # dropped by default for readability


def generate_password(text: str = "") -> str:
    t = (text or "").lower()
    m = re.search(r"\b(\d{1,3})\b", t)
    length = int(m.group(1)) if m else 16
    length = max(6, min(length, 64))

    pools = []
    pools.append(string.ascii_lowercase)
    if "no caps" not in t and "sirf small" not in t:
        pools.append(string.ascii_uppercase)
    if "no number" not in t and "bina number" not in t:
        pools.append(string.digits)
    want_sym = not any(k in t for k in
                       ("no symbol", "bina symbol", "simple", "easy", "alphanumeric"))
    if want_sym:
        pools.append("!@#$%^&*-_=+?")

    alphabet = "".join(pools)
    if "readable" in t or "clear" in t or "easy" in t:
        alphabet = "".join(c for c in alphabet if c not in _AMBIG)

    # guarantee at least one char from each pool
    while True:
        pw = [secrets.choice(p) for p in pools]
        pw += [secrets.choice(alphabet) for _ in range(length - len(pools))]
        secrets.SystemRandom().shuffle(pw)
        out = "".join(pw)[:length]
        if len(set(out)) >= min(4, length):  # avoid degenerate repeats
            break
    return f"Password ({length} chars): {out}"


_ALGOS = ("sha256", "sha1", "md5", "sha512")


def text_hash(text: str) -> Optional[str]:
    t = text or ""
    algo = "sha256"
    for a in _ALGOS:
        if re.search(rf"\b{a}\b", t, re.IGNORECASE):
            algo = a
            break
    # quoted text is taken verbatim (hashing is exact — respect the quotes)
    q = re.search(r"[\"'](.+?)[\"']", t)
    if q:
        payload = q.group(1)
    else:
        # strip command + filler words, then collapse whitespace so leftover
        # gaps don't change the digest
        payload = re.sub(
            r"\b(hash|digest|nikaalo|nikalo|banao|karo|ka|ki|checksum|of|"
            r"sha256|sha1|sha512|md5|generate|compute|is|this|text|ye|yeh|"
            r"iska|for)\b", " ", t, flags=re.IGNORECASE)
        payload = re.sub(r"\s+", " ", payload).strip(" \"'")
    if len(payload) < 1:
        return "Kis text ka hash chahiye? Jaise 'hello ka sha256 nikaalo'."
    digest = hashlib.new(algo, payload.encode("utf-8")).hexdigest()
    return f"{algo.upper()} of '{payload}':\n{digest}"


def generate_uuid(text: str = "") -> str:
    t = (text or "").lower()
    m = re.search(r"\b(\d{1,2})\b", t)
    n = max(1, min(int(m.group(1)), 10)) if m else 1
    ids = [str(uuid.uuid4()) for _ in range(n)]
    if n == 1:
        return f"UUID: {ids[0]}"
    return "UUIDs:\n" + "\n".join(ids)
