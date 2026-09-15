"""Password generator + text hash + UUID. Pure stdlib, offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="password_generate",
    description="Generate a strong random password (offline, crypto-random).",
    patterns=[
        "strong password banao", "password generate karo",
        "ek password bana do", "16 character ka password banao",
        "random password chahiye", "secure password bana do",
        "naya password generate karo",
    ],
    required_entities=[],
)
def password_generate(slots: dict) -> str:
    from core.gen_tools import generate_password
    return generate_password(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="text_hash",
    description="Compute a hash/checksum (sha256/md5/sha1) of text (offline).",
    patterns=[
        "iska sha256 nikaalo", "hello ka md5 banao", "text ka hash nikaalo",
        "checksum nikaalo", "sha1 hash karo", "is text ka digest banao",
        "md5 hash generate karo",
    ],
    required_entities=[],
)
def text_hash(slots: dict) -> str:
    from core.gen_tools import text_hash as _th
    return _th(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="uuid_generate",
    description="Generate one or more random UUIDs (offline).",
    patterns=[
        "ek uuid banao", "uuid generate karo", "random id chahiye",
        "unique id bana do", "3 uuid generate karo", "guid banao",
    ],
    required_entities=[],
)
def uuid_generate(slots: dict) -> str:
    from core.gen_tools import generate_uuid
    return generate_uuid(slots.get("raw_text") or slots.get("text") or "")
