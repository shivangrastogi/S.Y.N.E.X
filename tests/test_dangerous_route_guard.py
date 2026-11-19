"""Locks in JarvisMainEngine._guard_dangerous_route — the conditional safety net
that rescues clearly-signalled requests which the k-NN classifier dropped onto an
absurd or DESTRUCTIVE skill (measured via tools/validate_command_routing.py, 2026-08-01).

The guard is deliberately conditional: it fires only when a clear signal landed
OUTSIDE the relevant skill family, so correct routes (weather_for_city for a city
query, a genuine reminder) are never disturbed. That two-sidedness — rescue the
broken, preserve the correct — is exactly what these tests pin.

Bound to a lightweight stub (borrowing the class-level _REMINDER_FAMILY + the
unbound methods) so it runs pure in the fast lane — no engine construction.
"""
from __future__ import annotations

import pytest

from core.main_engine import JarvisMainEngine as _J
from core.intent_classifier import Prediction


class _Stub:
    _REMINDER_FAMILY = _J._REMINDER_FAMILY
    _force_intent = _J._force_intent
    _guard_dangerous_route = _J._guard_dangerous_route


_stub = _Stub()


def _route(text: str, current_intent: str) -> str:
    """What the guard turns `current_intent` into for `text`."""
    pred = Prediction(intent=current_intent, confidence=0.5,
                      top3=[(current_intent, 0.5)],
                      raw_text=text, normalized_text=text)
    return _stub._guard_dangerous_route(text, pred).intent


# ── rescue: a clear signal on the WRONG (often destructive) skill ───────
@pytest.mark.parametrize("text,wrong,expected", [
    # weather → set_reminder would CREATE a reminder — the dangerous one.
    ("mausam kaisa rahega", "set_reminder", "weather_local"),
    ("kal ka mausam kaisa hoga", "day_of_week", "weather_local"),
    ("baarish hone wali hai kya", "detect_holding", "weather_local"),
    ("mausam ka haal batao", "fun_fact", "weather_local"),
    ("kitni garmi hai aaj", "age_calc", "weather_local"),
    # system status → unrelated skills.
    ("system info batao", "whoami_info", "system_stats"),
    ("cpu aur ram batao", "work_power", "system_stats"),
    ("system ka haal batao", "fun_fact", "system_stats"),
    ("performance batao", "brain_health", "system_stats"),
    # screenshot → repeat_last.
    ("ss lelo", "repeat_last", "screenshot_full"),
    # note-creation → unrelated skills. add_expense is the harmful one (a note
    # request logging a junk expense).
    ("likho ye note grocery list", "add_expense", "create_note"),
    ("note create karo shopping items", "add_expense", "create_note"),
    ("note save karo password hint", "password_generate", "create_note"),
    ("meri note me add karo", "calculate", "create_note"),
    ("note banao meeting ke points", "todays_meetings", "create_note"),
    ("add a note about the project", "open_explorer_here", "create_note"),
    # a clear reminder request that landed outside the reminder family.
    ("kal subah gym jaana yaad dilana", "doc_answer", "set_reminder"),
    ("yaad dilana bill bharne ka", "empty_recycle_bin", "set_reminder"),
    # clear_chat is DESTRUCTIVE — a pep-talk request must not wipe the chat.
    ("ek pep talk do", "clear_chat", "ask_jarvis"),
    ("motivate me", "clear_memory", "ask_jarvis"),
    # brainstorm scatter (add_expense = a junk expense) → brainstorm_ideas.
    ("suggest some ideas for dinner", "add_expense", "brainstorm_ideas"),
    ("youtube channel ke ideas do", "play_youtube", "brainstorm_ideas"),
    ("ideas batao date night ke", "current_date", "brainstorm_ideas"),
    # pre-existing guards still hold.
    ("mujhe kal yaad dila dena", "dice_roll", "set_reminder"),
    ("amazon.com kholo", "add_expense", "open_website"),
    # note CREATE on the summariser (it summarised instead of creating).
    ("ek note create karo", "scratchpad_summarize", "create_note"),
    # 2026-09-15: measured through the real route() chain.
    ("is it going to rain", "regenerate_skill_docs", "weather_local"),
    ("temperature kitna hai", "quick_math", "weather_local"),
    ("ram kitni use ho rahi hai", "age_calc", "system_stats"),
    ("cpu temperature batao", "get_weather", "system_stats"),
    ("grab the screen", "read_screen", "screenshot_full"),
    ("note me daal do ye", "lock_after", "create_note"),
])
def test_guard_rescues_broken_route(text, wrong, expected):
    assert _route(text, wrong) == expected


def _route_none(text: str):
    pred = Prediction(intent=None, confidence=0.1, top3=[],
                      raw_text=text, normalized_text=text)
    return _stub._guard_dangerous_route(text, pred).intent


def test_guard_rescues_explicit_note_with_no_prediction():
    # Fell through to chat before: nothing cleared any routing tier.
    assert _route_none("note me likho call the plumber") == "create_note"


@pytest.mark.parametrize("text", [
    "garmi lag rahi hai yaar",     # weather word, but a remark, not a request
    "system bahut slow hai",       # system word, no stats request
    "kal yaad dilana",             # reminder rule needs a prediction to correct
])
def test_guard_leaves_unpredicted_chat_alone(text):
    assert _route_none(text) is None


# ── preserve: a correct route must pass through unchanged ───────────────
@pytest.mark.parametrize("text,correct", [
    ("delhi ka weather", "weather_for_city"),   # city query → NOT flattened
    ("aaj ka weather", "weather_local"),
    ("cpu usage kitna hai", "system_stats"),
    ("disk space kitna bacha hai", "disk_space"),
    ("memory usage kya hai", "memory_stats"),
    ("screenshot lo", "screenshot_full"),
    ("window ka screenshot", "screenshot_window"),
    ("kal 9 baje reminder set karo", "set_reminder"),  # a real reminder
    ("tell me a joke", "tell_joke"),
    ("2 plus 2 kitna hai", "calculate"),
    ("append_note me daalo", "append_note"),           # already note-family
    ("500 rupaye kharch note kiya", "add_expense"),    # a real expense, not a note
    ("footnote add karo", "add_task"),                 # \bnote\b won't match footnote
    ("chat clear karo", "clear_chat"),                 # explicit wipe → kept
    ("purani baatein hata do", "clear_chat"),          # explicit wipe → kept
    ("reset the conversation", "clear_chat"),          # explicit wipe → kept
    ("play some music", "play_music"),                 # not a brainstorm/ideas req
    ("no ideas came to mind", "tell_joke"),            # "ideas" without a give-verb
    ("notes ka summary banao", "scratchpad_summarize"),  # a real summary request
    ("cpu temperature batao", "system_stats"),         # a cpu temp is not weather
    ("30 celsius temperature convert karo", "unit_convert"),
    ("ram kitna kamata hai", "ask_jarvis"),            # Ram the person
])
def test_guard_preserves_correct_route(text, correct):
    assert _route(text, correct) == correct
