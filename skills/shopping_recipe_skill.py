"""Unit-price compare (pure math) + recipe suggest (local LLM). Offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="unit_price_compare",
    description="Compare two pack sizes by price-per-unit to find the better deal (offline).",
    patterns=[
        "kaunsa sasta hai", "unit price compare karo", "better deal kaunsa",
        "500ml 40 vs 1 litre 70", "per unit price batao",
        "konsa deal accha hai", "sasta kaunsa padega",
    ],
    required_entities=[],
)
def unit_price_compare(slots: dict) -> str:
    from core.shopping_math import compare
    out = compare(slots.get("raw_text") or slots.get("text") or "")
    return out or ("Do options do — jaise '500ml 40 rupaye vs 1 litre 70' — "
                   "main per-unit sasta bata dunga.")


@skill(
    name="recipe_suggest",
    description="Suggest a simple recipe or what to cook, using the local model (offline).",
    patterns=[
        "recipe batao", "kya banau", "iski recipe do", "khana kya banau",
        "recipe suggest karo", "aaj kya cook karu", "koi easy recipe batao",
    ],
    required_entities=[],
)
def recipe_suggest(slots: dict) -> str:
    from skills.llm_utils_skill import _gen, _drop_words, _NO_MODEL
    raw = slots.get("raw_text") or slots.get("text") or ""
    have = _drop_words(raw, {"recipe", "batao", "kya", "banau", "banaun",
                             "iski", "do", "khana", "suggest", "karo", "aaj",
                             "cook", "karu", "koi", "easy", "se", "ke", "ki",
                             "me", "mein"})
    ctx = f" using: {have}" if len(have) > 2 else ""
    out = _gen(f"Suggest ONE simple recipe{ctx}.",
               system=("Give a dish name + 4-6 short numbered steps. Keep it "
                       "simple and quick. Hinglish theek hai. No preamble."),
               max_tokens=280)
    return out.strip() if out else _NO_MODEL
