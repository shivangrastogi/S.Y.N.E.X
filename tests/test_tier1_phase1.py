"""Tier 1 phase 1 — presence, Outlook calendar/email, TTS voice switch,
notification mirror.

Side-effect-safe:
  * presence tests stub the recognizer + VisionEngine so no camera opens.
  * Outlook tests stub win32com.Dispatch so no real Outlook process spawns.
  * TTS voice tests use monkeypatched settings.
  * Notification mirror tests don't actually start the WinRT poll.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "presence_status", "presence_auto_pause_on", "presence_auto_pause_off",
    "next_meeting", "todays_meetings", "this_week_meetings",
    "compose_email", "email_draft_blank",
    "tts_voice_set", "tts_voice_list", "tts_voice_status", "tts_voice_reset",
    "notification_mirror_on", "notification_mirror_off",
    "last_notification", "notification_mirror_status",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── brain routing ─────────────────────────────────────────────────

ROUTING_CASES = [
    ("presence status",                "presence_status"),
    ("presence auto pause on",         "presence_auto_pause_on"),
    ("presence auto pause off",        "presence_auto_pause_off"),
    ("next meeting",                   "next_meeting"),
    ("todays meetings",                "todays_meetings"),
    ("this week meetings",             "this_week_meetings"),
    ("compose email",                  "compose_email"),
    ("blank email",                    "email_draft_blank"),
    ("set voice to",                   "tts_voice_set"),
    ("use hindi voice",                "tts_voice_set"),
    ("list voices",                    "tts_voice_list"),
    ("current tts voice",              "tts_voice_status"),
    ("reset tts voice",                "tts_voice_reset"),
    ("notification mirror on",         "notification_mirror_on"),
    ("read my notifications",          "notification_mirror_on"),
    ("notification mirror off",        "notification_mirror_off"),
    ("last notification",              "last_notification"),
    ("notification mirror status",     "notification_mirror_status"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_tier1(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── presence ─────────────────────────────────────────────────────


def test_presence_status_when_off():
    from skills.presence_skill import presence_status
    out = presence_status({})
    assert "OFF" in out or "off" in out.lower()


def test_presence_engine_transitions(monkeypatch):
    """Synthesise frames + face hits → engine should flip present/absent."""
    from core import presence
    # Reset singleton for the test.
    presence._DEFAULT = None
    eng = presence.get_presence_engine()
    # Spy on listener fan-out.
    events: list[str] = []
    eng.add_listener(events.append)

    # Stub the recognizer.
    name_sequence = [["shivang"], ["shivang"], [], [], [], [], []]

    class _Rec:
        def is_available(self): return True
        def identify_faces(self, _frame): return name_sequence.pop(0)

    monkeypatch.setattr("core.face_recognition.get_recognizer", lambda: _Rec())
    # Force probe each call by zeroing the cadence.
    monkeypatch.setattr(presence, "_PROBE_INTERVAL_S", 0.0)
    monkeypatch.setattr(presence, "_ABSENCE_GRACE_S", 0.0)

    fake = object()
    eng._on_frame(fake)          # face present
    assert eng.is_present() is True
    assert events[-1] == "present"
    eng._on_frame(fake)          # still present, no new event
    eng._on_frame(fake)          # no face — grace 0 → absent fires
    assert eng.is_present() is False
    assert events[-1] == "absent"


# ── Outlook calendar (no real Outlook spawn) ─────────────────────


class _FakeAppointment:
    def __init__(self, subject, start, location=""):
        self.Subject = subject
        self.Start = start
        self.Location = location


def test_next_meeting_when_outlook_unreachable(monkeypatch):
    import skills.outlook_calendar as oc
    monkeypatch.setattr(oc, "_outlook_calendar", lambda: None)
    out = oc.next_meeting({})
    assert "reach nahi" in out.lower() or "outlook" in out.lower()


def test_next_meeting_returns_first(monkeypatch):
    import skills.outlook_calendar as oc
    from datetime import datetime, timedelta
    fake_cal = object()
    monkeypatch.setattr(oc, "_outlook_calendar", lambda: fake_cal)
    soon = datetime.now() + timedelta(hours=1)
    monkeypatch.setattr(oc, "_query_appointments",
                        lambda s, e: iter([_FakeAppointment("Standup", soon, "Zoom")]))
    out = oc.next_meeting({})
    assert "Standup" in out
    assert "Zoom" in out


def test_todays_meetings_empty(monkeypatch):
    import skills.outlook_calendar as oc
    monkeypatch.setattr(oc, "_outlook_calendar", lambda: object())
    monkeypatch.setattr(oc, "_query_appointments", lambda s, e: iter([]))
    out = oc.todays_meetings({})
    assert "koi meeting" in out.lower() or "nahi" in out.lower()


# ── Outlook email ────────────────────────────────────────────────


def test_email_parses_parts():
    from skills.outlook_email import _parse
    r, s, b = _parse("compose email to alice subject status update body all good")
    assert r.lower() in ("alice", "alice ")
    assert "status update" in s
    assert "all good" in b


def test_email_when_outlook_unreachable(monkeypatch):
    import skills.outlook_email as oe
    monkeypatch.setattr(oe, "_open_outlook", lambda: None)
    out = oe.compose_email({"raw_text": "compose email to alice"})
    assert "outlook" in out.lower() or "reach nahi" in out.lower()


def test_email_dispatches_to_outlook(monkeypatch):
    """When _open_outlook returns a fake app, the skill should create and
    Display a draft with the parsed fields populated."""
    import skills.outlook_email as oe

    class _Mail:
        def __init__(self):
            self.To = ""
            self.Subject = ""
            self.HTMLBody = ""
            self.displayed = False
        def Display(self, modal):
            self.displayed = True

    mail = _Mail()

    class _App:
        def CreateItem(self, kind):
            return mail

    monkeypatch.setattr(oe, "_open_outlook", lambda: _App())
    out = oe.compose_email({"raw_text": "compose email to bob subject hello body hi"})
    assert mail.To.lower().startswith("bob")
    assert "hello" in mail.Subject
    assert "hi" in mail.HTMLBody
    assert mail.displayed is True
    assert "Outlook draft" in out


# ── TTS voice ────────────────────────────────────────────────────


def test_voice_alias_resolver():
    from skills.tts_voice import _resolve_voice
    assert _resolve_voice("use hindi voice") == "hi-IN-SwaraNeural"
    assert _resolve_voice("switch to american female") == "en-US-AriaNeural"
    assert _resolve_voice("speak in hindi") == "hi-IN-SwaraNeural"
    assert _resolve_voice("set voice to british male") == "en-GB-RyanNeural"
    assert _resolve_voice("female voice") == "en-IN-NeerjaNeural"
    assert _resolve_voice("nothing recognisable") is None


def test_voice_raw_neural_id_pass_through():
    from skills.tts_voice import _resolve_voice
    # Raw Edge-TTS voice ids should pass through with case preserved
    # — Edge-TTS treats voice ids case-sensitively.
    assert _resolve_voice("hi-IN-SwaraNeural") == "hi-IN-SwaraNeural"
    assert _resolve_voice("en-US-AriaNeural") == "en-US-AriaNeural"


def test_voice_set_persists(monkeypatch):
    state: dict = {}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    from skills.tts_voice import tts_voice_set, tts_voice_status
    out = tts_voice_set({"raw_text": "use american female"})
    assert state["tts_voice"] == "en-US-AriaNeural"
    assert "en-US-AriaNeural" in out
    status = tts_voice_status({})
    assert "en-US-AriaNeural" in status


def test_voice_list_returns_voices():
    from skills.tts_voice import tts_voice_list
    out = tts_voice_list({})
    assert "TTS voices" in out
    assert "hi-IN-SwaraNeural" in out
    assert "en-US-AriaNeural" in out


def test_tts_engine_reads_live_voice(monkeypatch):
    from core import tts
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: "en-US-AriaNeural" if k == "tts_voice" else d)
    assert tts._live_tts_voice() == "en-US-AriaNeural"


def test_tts_engine_voice_default_when_empty(monkeypatch):
    from core import tts
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: "" if k == "tts_voice" else d)
    assert tts._live_tts_voice() is None


# ── notification mirror (no real winrt) ──────────────────────────


def test_notification_status_reports_availability():
    from skills.notification_mirror import notification_mirror_status
    out = notification_mirror_status({})
    assert "mirror" in out.lower()
    # Either "available" or "UNAVAILABLE" — depends on winrt being installed.
    assert "available" in out.lower() or "unavailable" in out.lower()


def test_notification_mirror_on_handles_missing_winrt(monkeypatch):
    from core import notify_listener as nl
    from skills.notification_mirror import notification_mirror_on
    monkeypatch.setattr(nl, "_winrt_import", lambda: None)
    out = notification_mirror_on({})
    assert "winrt" in out.lower() or "winsdk" in out.lower()


def test_last_notification_when_none():
    from core.notify_listener import get_listener
    from skills.notification_mirror import last_notification
    get_listener()._last = None
    out = last_notification({})
    # Either "no notification yet" or "install winsdk" depending on env.
    assert "notification" in out.lower() or "install" in out.lower()


def test_install_speaker_hook_idempotent():
    """Calling install_speaker_hook twice should only attach once."""
    from core.notify_listener import get_listener, install_speaker_hook
    eng = get_listener()
    # Clear listeners first.
    with eng._lock:
        eng._listeners.clear()
    install_speaker_hook()
    install_speaker_hook()
    install_speaker_hook()
    hooks = [fn for fn in eng._listeners
             if getattr(fn, "_aeris_speaker_hook", False)]
    assert len(hooks) == 1
