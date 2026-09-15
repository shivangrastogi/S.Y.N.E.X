"""Security helpers — password strength (offline).

password_generate already exists; this is the checker. Fully local
entropy estimate (core/finance_math.password_strength).
"""
from __future__ import annotations

from core.skill_registry import skill

# Command words stripped from the FRONT to isolate the password. A regex
# only stripped one of {strength, check} and mistook "check karo" for the
# password — token-drop is robust to any word order.
_CMD_WORDS = {
    "password", "paasword", "pass", "strength", "check", "karo", "kitna",
    "strong", "hai", "kya", "is", "ki", "batao", "ya", "nahi", "ye", "yeh",
    "mera", "meri", "the", "of", "this",
}


def _extract_pw(text: str) -> str:
    tokens = (text or "").split()
    while tokens and tokens[0].strip(":-").lower() in _CMD_WORDS:
        tokens.pop(0)
    return " ".join(tokens).strip(":- ")


@skill(
    name="password_strength",
    description="Rate how strong a password is — length, character mix, entropy (offline).",
    patterns=[
        "password kitna strong hai", "password strength check karo",
        "ye password strong hai kya", "mera password check karo",
        "is password ki strength batao", "password strong hai ya nahi",
        "check password strength",
    ],
    required_entities=[],
)
def password_strength(slots: dict) -> str:
    from core.finance_math import password_strength as _ps
    text = slots.get("raw_text") or slots.get("text") or ""
    pw = _extract_pw(text)
    if not pw or len(pw) < 2:
        return ("Kaunsa password check karun, sir? Bolo 'password strength "
                "check karo <password>'. (Local check — kahin bheja nahi "
                "jaata.)")
    return _ps(pw)
