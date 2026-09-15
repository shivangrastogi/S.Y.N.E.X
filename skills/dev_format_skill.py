"""JSON format/validate + URL encode-decode + slugify. Stdlib, offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="json_format",
    description="Pretty-print, minify or validate a JSON string (offline).",
    patterns=[
        "json format karo", "json pretty print karo", "json validate karo",
        "json minify karo", "is json ko sundar banao", "json check karo",
        "json beautify karo",
    ],
    required_entities=[],
)
def json_format(slots: dict) -> str:
    from core.dev_format import json_format as _jf
    return _jf(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="url_convert",
    description="URL-encode or URL-decode text (offline).",
    patterns=[
        "url encode karo", "url decode karo", "isko url encode kar do",
        "percent encode karo", "url me convert karo", "url decode kar do",
    ],
    required_entities=[],
)
def url_convert(slots: dict) -> str:
    from core.dev_format import url_convert as _uc
    return _uc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="slugify",
    description="Make a URL-friendly slug from a title (offline).",
    patterns=[
        "slug banao", "slugify karo", "url slug bana do", "iska slug banao",
        "title ka slug nikaalo", "seo slug banao",
    ],
    required_entities=[],
)
def slugify(slots: dict) -> str:
    from core.dev_format import slugify as _sl
    return _sl(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="id_validate",
    description="Check PAN / IFSC / PIN-code format validity (offline, format only).",
    patterns=[
        "ABCDE1234F pan valid hai kya", "id validate karo",
        "ifsc code sahi hai kya", "pincode format check karo",
        "pan number valid hai", "ye ifsc valid hai",
    ],
    required_entities=[],
)
def id_validate(slots: dict) -> str:
    from core.dev_format import id_validate as _iv
    return _iv(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="luhn_check",
    description="Validate a number by the Luhn checksum (cards, IMEI, etc.) (offline).",
    patterns=[
        "79927398713 luhn valid hai kya", "luhn check karo",
        "ye card number valid checksum hai", "luhn algorithm check",
        "number ka checksum sahi hai", "luhn se validate karo",
    ],
    required_entities=[],
)
def luhn_check(slots: dict) -> str:
    from core.dev_format import luhn_check as _lc
    return _lc(slots.get("raw_text") or slots.get("text") or "")
