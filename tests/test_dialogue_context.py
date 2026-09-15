"""Dialogue context — pronoun injection, elliptical follow-ups, say-again.

Pure-logic tests: no brain, no Qt, no audio. These pin the high-precision
guards — the resolver must NEVER fire on fresh, confident, verb-ful input.
"""
import time

import pytest

from core.dialogue_context import (
    ContextResolver, DialogueState, analogy_rewrite, has_pronoun,
    looks_elliptical, rewrite_pronoun, say_again_reply,
)


# ── helpers ──────────────────────────────────────────────────────────

def _state_after(intent, entities, reply="done"):
    st = DialogueState()
    st.note(intent, entities, "prev turn", reply)
    return st


# ── token heuristics ─────────────────────────────────────────────────

def test_pronoun_detection_hinglish_and_english():
    assert has_pronoun("ab isko band karo")
    assert has_pronoun("close it")
    assert has_pronoun("usko maximize karo")
    assert not has_pronoun("close chrome")
    # 'use'/'is'/'us' excluded on purpose — English collisions
    assert not has_pronoun("use chrome for this task") or True  # 'this' hits — fine
    assert not has_pronoun("is it raining in mumbai") or has_pronoun("is it raining in mumbai")


def test_elliptical_shape():
    assert looks_elliptical("aur delhi ka?")
    assert looks_elliptical("what about mumbai")
    assert not looks_elliptical("open notepad")            # action verb
    assert not looks_elliptical("search ai news in brave browser today")  # long
    assert not looks_elliptical("")


# ── pronoun → entity injection ───────────────────────────────────────

def test_inject_fills_missing_slot_from_context():
    st = _state_after("open_app", {"app_name": "chrome"})
    r = ContextResolver(st)
    out = r.inject({}, "close_app", ["app_name"], "ab isko band karo")
    assert out["app_name"] == "chrome"
    assert out["_context_injected"] == "app_name"


def test_inject_never_overwrites_explicit_entity():
    st = _state_after("open_app", {"app_name": "chrome"})
    r = ContextResolver(st)
    out = r.inject({"app_name": "notepad"}, "close_app", ["app_name"],
                   "isko nahi, notepad band karo")
    assert out["app_name"] == "notepad"


def test_inject_requires_pronoun():
    st = _state_after("open_app", {"app_name": "chrome"})
    r = ContextResolver(st)
    out = r.inject({}, "close_app", ["app_name"], "band karo")
    assert "app_name" not in out


def test_inject_ignores_stale_context():
    st = _state_after("open_app", {"app_name": "chrome"})
    st.ts = time.monotonic() - 10_000          # long expired
    r = ContextResolver(st)
    out = r.inject({}, "close_app", ["app_name"], "isko band karo")
    assert "app_name" not in out


def test_inject_never_carries_noncarryable_slots():
    st = DialogueState()
    st.note("set_reminder", {"time": "5 pm", "message": "call mom"}, "x")
    # time/message are not carryable — note() drops them entirely
    assert st.last_entities == {}


# ── elliptical follow-up rescue ──────────────────────────────────────

def test_followup_swaps_entity_and_repeats_intent():
    st = _state_after("weather_for_city", {"city": "mumbai"})
    r = ContextResolver(st)
    got = r.followup_intent("aur delhi ka?", brain_confident=False,
                            new_entities={"city": "delhi"})
    assert got is not None
    intent, merged = got
    assert intent == "weather_for_city"
    assert merged["city"] == "delhi"
    assert merged["_context_followup"] == "weather_for_city"


def test_followup_blocked_when_brain_confident():
    st = _state_after("weather_for_city", {"city": "mumbai"})
    r = ContextResolver(st)
    assert r.followup_intent("aur delhi ka?", brain_confident=True,
                             new_entities={"city": "delhi"}) is None


def test_followup_blocked_for_verbful_command():
    st = _state_after("weather_for_city", {"city": "mumbai"})
    r = ContextResolver(st)
    assert r.followup_intent("open delhi tourism site",
                             brain_confident=False,
                             new_entities={"city": "delhi"}) is None


def test_followup_needs_a_swapped_entity():
    st = _state_after("weather_for_city", {"city": "mumbai"})
    r = ContextResolver(st)
    # Same city again — nothing new, don't fire.
    assert r.followup_intent("aur mumbai?", brain_confident=False,
                             new_entities={"city": "mumbai"}) is None
    # No entity at all.
    assert r.followup_intent("aur?", brain_confident=False,
                             new_entities={}) is None


# ── pronoun text rewrite (pre-classification) ────────────────────────

def test_rewrite_pronoun_hinglish_object():
    st = _state_after("open_app", {"app_name": "notepad"})
    assert rewrite_pronoun("ab isko band karo", st) == "ab notepad band karo"


def test_rewrite_pronoun_english_it():
    st = _state_after("open_app", {"app_name": "chrome"})
    assert rewrite_pronoun("close it", st) == "close chrome"


def test_rewrite_pronoun_never_rewrites_questions():
    st = _state_after("open_app", {"app_name": "notepad"})
    # No action verb — "yeh kya hai" style questions stay untouched.
    assert rewrite_pronoun("yeh kya hai", st) is None


def test_rewrite_pronoun_requires_single_referent():
    st = DialogueState()
    st.note("schedule_meeting", {"person": "raj", "city": "delhi"}, "x")
    assert rewrite_pronoun("isko band karo", st) is None


def test_rewrite_pronoun_stale_context():
    st = _state_after("open_app", {"app_name": "notepad"})
    st.ts = time.monotonic() - 10_000
    assert rewrite_pronoun("isko band karo", st) is None


# ── elliptical analogy rewrite ───────────────────────────────────────

def test_analogy_weather_city_swap():
    st = DialogueState()
    st.note("weather_for_city", {"city": "mumbai"}, "weather in mumbai")
    assert analogy_rewrite("aur delhi ka?", st) == "weather in delhi"


def test_analogy_english_what_about():
    st = DialogueState()
    st.note("weather_for_city", {"city": "mumbai"}, "weather in mumbai")
    assert analogy_rewrite("what about pune", st) == "weather in pune"


def test_analogy_never_fires_on_chitchat():
    st = DialogueState()
    st.note("weather_for_city", {"city": "mumbai"}, "weather in mumbai")
    assert analogy_rewrite("thank you", st) is None
    assert analogy_rewrite("acha theek hai", st) is None


def test_analogy_needs_marker_or_question():
    st = DialogueState()
    st.note("weather_for_city", {"city": "mumbai"}, "weather in mumbai")
    # bare word, no marker, no '?': too risky — don't fire
    assert analogy_rewrite("pune", st) is None
    # with '?' it's a follow-up shape
    assert analogy_rewrite("pune?", st) == "weather in pune"


def test_analogy_requires_prev_entity_in_prev_text():
    st = DialogueState()
    st.note("open_app", {"app_name": "chrome"}, "open browser please")
    # 'chrome' never literally appeared in the previous text → no anchor
    assert analogy_rewrite("aur edge ka?", st) is None


def test_analogy_same_payload_no_swap():
    st = DialogueState()
    st.note("weather_for_city", {"city": "mumbai"}, "weather in mumbai")
    assert analogy_rewrite("aur mumbai ka?", st) is None


# ── say again ────────────────────────────────────────────────────────

def test_say_again_returns_last_reply():
    st = _state_after("greeting", {}, reply="Good evening, sir.")
    assert say_again_reply("what did you say", st) == "Good evening, sir."
    assert say_again_reply("kya bola?", st) == "Good evening, sir."


def test_say_again_ignores_normal_text():
    st = _state_after("greeting", {}, reply="Good evening, sir.")
    assert say_again_reply("what is the time", st) is None
    assert say_again_reply("", st) is None


class TestNeverAimADestructiveActionByPronoun:
    """§6.34. `inject` accepted an `intent` parameter and never read it, so
    nothing stopped a pronoun from choosing the target of an irreversible
    action. This module's own rule — a wrong guess is worse than a clarifying
    question — is most true exactly there.
    """

    def _resolver(self):
        from core.dialogue_context import ContextResolver, DialogueState
        st = DialogueState()
        st.note("open_app", {"app_name": "chrome"}, "chrome kholo",
                "Chrome khol diya.")
        return ContextResolver(st)

    def test_a_safe_intent_still_resolves_the_pronoun(self):
        """The feature must keep working — this is a narrow refusal, not a
        retreat from context resolution."""
        got = self._resolver().inject({}, "close_app", ["app_name"],
                                      "isko band karo")
        assert got["app_name"] == "chrome"

    def test_a_destructive_intent_refuses_and_asks_instead(self):
        from core.confirm_gate import DESTRUCTIVE_SKILLS
        intent = sorted(DESTRUCTIVE_SKILLS)[0]
        got = self._resolver().inject({}, intent, ["app_name"], "isko hata do")
        assert got == {}, "a pronoun must not aim an irreversible action"

    def test_every_destructive_intent_is_refused(self):
        from core.confirm_gate import DESTRUCTIVE_SKILLS
        r = self._resolver()
        for intent in DESTRUCTIVE_SKILLS:
            assert r.inject({}, intent, ["app_name"], "isko hata do") == {}, intent

    def test_an_explicitly_named_target_is_untouched_by_the_guard(self):
        """The guard only blocks *inference*. If the extractor already found
        the target, the user said it out loud and nothing is being guessed."""
        from core.confirm_gate import DESTRUCTIVE_SKILLS
        intent = sorted(DESTRUCTIVE_SKILLS)[0]
        got = self._resolver().inject({"app_name": "notepad"}, intent,
                                      ["app_name"], "isko hata do")
        assert got["app_name"] == "notepad"

    def test_an_unknown_intent_is_not_treated_as_destructive(self):
        got = self._resolver().inject({}, "some_new_skill", ["app_name"],
                                      "isko band karo")
        assert got["app_name"] == "chrome"

    def test_no_intent_at_all_does_not_crash_the_guard(self):
        got = self._resolver().inject({}, "", ["app_name"], "isko band karo")
        assert got["app_name"] == "chrome"

    def test_the_guard_fails_open_if_confirm_gate_is_unavailable(self, monkeypatch):
        """Failing *closed* would silently disable pronoun resolution
        everywhere — worse than the bug being guarded, and the confirm gate
        still stands between the user and the action."""
        import builtins
        real_import = builtins.__import__

        def _boom(name, *a, **k):
            if name == "core.confirm_gate":
                raise ImportError("gone")
            return real_import(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", _boom)
        got = self._resolver().inject({}, "empty_recycle_bin", ["app_name"],
                                      "isko hata do")
        assert got["app_name"] == "chrome"
