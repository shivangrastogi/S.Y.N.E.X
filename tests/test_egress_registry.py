"""A module cannot gain network access without saying so (§6.38).

P4 asks for "everything local". The brain genuinely is. The ears and voice are
not — every spoken turn sends audio to Google and reply text to Microsoft —
and until `docs/PRIVACY.md` existed there was no findable account of that.
§6.28 is what the absence cost: a "must not leave the machine" claim about the
sleeping mic that the code did not implement, with nothing in the repo to
contradict it.

These tests make the account self-maintaining: a new skill that phones home
fails the suite instead of shipping quietly.
"""

from __future__ import annotations

import pathlib

from core.egress_registry import (
    DESCRIPTIONS, LOCAL, OPTIONAL, REMOTE, discover_egress, remote_modules,
    render_markdown, stale, undocumented,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestTheGuard:
    def test_no_module_reaches_the_network_undocumented(self):
        missing = undocumented()
        assert not missing, (
            f"{len(missing)} module(s) can reach the network with no entry in "
            f"core/egress_registry.py: {missing}. Describe what each sends — "
            f"an undocumented network call is how 'everything local' stops "
            f"being true.")

    def test_no_entry_outlives_its_module(self):
        gone = stale()
        assert not gone, (
            f"described but no longer network-capable: {gone}. Remove them, "
            f"or the privacy doc overstates what leaves.")

    def test_every_entry_is_fully_specified(self):
        for module, entry in DESCRIPTIONS.items():
            assert len(entry) == 4, module
            scope, dest, sends, avoid = entry
            assert scope in (LOCAL, REMOTE, OPTIONAL), module
            assert dest.strip() and sends.strip() and avoid.strip(), module


class TestTheHeadlineFacts:
    """Pinned deliberately. If one of these ever stops being true it is a
    significant change in what AERIS is, and it should be a deliberate edit
    with a failing test in front of it — not a quiet drift."""

    def test_speech_recognition_is_still_a_remote_dependency(self):
        assert DESCRIPTIONS["core/stt.py"][0] == REMOTE
        assert "core/stt.py" in remote_modules()

    def test_spoken_replies_still_leave_the_machine(self):
        assert DESCRIPTIONS["core/tts.py"][0] == REMOTE

    def test_the_local_llm_is_marked_local(self):
        """Ollama on 127.0.0.1 is the thing that makes 'no cloud brain' true."""
        scope, dest, _sends, _avoid = DESCRIPTIONS["core/llm_chat.py"]
        assert scope == LOCAL and "127.0.0.1" in dest

    def test_the_phone_bridge_says_it_encrypts_before_upload(self):
        _s, _d, sends, _a = DESCRIPTIONS["core/cloud_bridge.py"]
        assert "encrypted" in sends.lower()

    def test_the_always_on_remote_set_is_exactly_what_we_expect(self):
        assert set(remote_modules()) == {
            "core/stt.py", "core/voice_engine.py", "core/tts.py",
            "core/cloud_bridge.py"}


class TestScannerPrecision:
    """A privacy document that cries wolf is one people learn to skip."""

    def test_urllib_parse_alone_is_not_egress(self):
        """Quoting a search term is string manipulation. Counting it flagged
        four modules that never touch the network."""
        found = discover_egress()
        for m in ("core/dev_format.py", "skills/web_jumps.py",
                  "skills/maps_gesture_skill.py", "skills/compute_skills.py"):
            assert m not in found, f"{m} only uses urllib.parse"

    def test_urllib_request_is_egress(self):
        found = discover_egress()
        assert "skills/weather_for_city.py" in found

    def test_lazily_imported_network_libraries_are_still_caught(self):
        """`ast.walk` descends into function bodies, so an import hidden
        inside a function is not a way to avoid the guard."""
        found = discover_egress()
        f = found.get("skills/system_health.py")
        assert f is not None
        assert any("urllib.request" in t or "socket" in t for t in f.triggers)

    def test_the_registry_does_not_scan_itself(self):
        """It names every network library as a string literal, so scanning it
        would report itself and every future addition."""
        assert "core/egress_registry.py" not in discover_egress()

    def test_each_finding_records_why(self):
        for m, e in discover_egress().items():
            assert e.triggers, m


class TestGeneratedDoc:
    def test_the_committed_doc_is_current(self):
        path = ROOT / "docs" / "PRIVACY.md"
        assert path.exists(), "run: python gen_privacy_doc.py"
        assert path.read_text(encoding="utf-8") == render_markdown(), (
            "docs/PRIVACY.md is out of date — run: python gen_privacy_doc.py")

    def test_it_leads_with_the_uncomfortable_part(self):
        """The headline is not 'AERIS is local'. It is that the brain is and
        the ears and voice are not."""
        out = render_markdown()
        head = out.split("## ", 1)[0]
        assert "ears and voice are not" in head

    def test_every_remote_module_tells_you_how_to_avoid_it(self):
        out = render_markdown()
        for m in remote_modules():
            assert f"`{m}`" in out
            assert DESCRIPTIONS[m][3].strip() not in ("", "-"), (
                f"{m} is always-on remote and must offer a way out")
