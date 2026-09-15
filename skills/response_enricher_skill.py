"""Voice surface for the response enricher: enable, disable, clear, status."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="enrich_responses_on",
    description="Enable LLM-backed response variation so stock replies stay fresh.",
    patterns=[
        "enable response enrichment", "responses enrich karo",
        "enable smart replies", "smart greeting on", "vary responses",
        "responses vary karo", "enrich responses",
        "turn on response enrichment", "enable reply variation",
    ],
    required_entities=[],
)
def enrich_responses_on(_slots: dict) -> str:
    from core import response_enricher
    response_enricher.set_enabled(True)
    avail = "and the LLM is reachable." if response_enricher._llm_available_safe() else "but LLM is offline — cached lines only."
    return f"Response enrichment ON {avail}"


@skill(
    name="enrich_responses_off",
    description="Disable LLM-backed response variation (use plain templates).",
    patterns=[
        "disable response enrichment", "responses enrich band karo",
        "turn off response enrichment", "disable smart replies",
        "plain replies", "use plain replies", "stop varying responses",
        "disable reply variation",
    ],
    required_entities=[],
)
def enrich_responses_off(_slots: dict) -> str:
    from core import response_enricher
    response_enricher.set_enabled(False)
    return "Response enrichment OFF — plain templates wapas chal rahe."


@skill(
    name="enrich_cache_clear",
    description="Forget all cached enriched replies and start fresh.",
    patterns=[
        "clear response cache", "response cache clear karo",
        "forget cached replies", "reset enriched replies",
        "wipe response cache", "enrich cache clear karo",
    ],
    required_entities=[],
)
def enrich_cache_clear(_slots: dict) -> str:
    from core import response_enricher
    n = response_enricher.clear_cache()
    return f"Cleared {n} cached replies. Fresh ones agle baar generate honge."


@skill(
    name="enrich_status",
    description="Report enrichment toggle, LLM availability, and cached counts.",
    patterns=[
        "response enrichment status", "enrich status",
        "are smart replies on", "reply enrichment kaisa chal raha",
        "response cache status",
    ],
    required_entities=[],
)
def enrich_status(_slots: dict) -> str:
    from core import response_enricher
    s = response_enricher.stats()
    state = "ON" if s["enabled"] else "OFF"
    llm = "reachable" if s["llm_available"] else "offline"
    top = ", ".join(f"{x['slot']}:{x['count']}" for x in s["slots"][:3]) or "empty"
    return (f"Enrichment {state}, LLM {llm}, cached lines {s['total']} "
            f"(top: {top}).")
