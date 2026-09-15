"""Tier 7 — phone-bridge HTTP server, telemetry aggregator/dashboard,
AR camera overlay.

Side-effect-safe:
  * Phone bridge tests spin a real server on an ephemeral port, use
    urllib for the round-trip, then call stop() in the teardown.
  * Telemetry tests stub the trace/workspace/face/kg subsystems so the
    snapshot is deterministic.
  * AR overlay tests only import the module + assert main-thread refusal.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.request

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "phone_pair_on", "phone_pair_off", "phone_pair_url",
    "open_telemetry_dashboard", "telemetry_digest",
    "ar_overlay_on", "ar_overlay_off", "ar_overlay_status",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("phone pair on",                "phone_pair_on"),
    ("start phone bridge",           "phone_pair_on"),
    ("phone pair off",               "phone_pair_off"),
    ("phone pair url",               "phone_pair_url"),
    ("open telemetry",               "open_telemetry_dashboard"),
    ("telemetry digest",             "telemetry_digest"),
    ("ar overlay on",                "ar_overlay_on"),
    ("show ar overlay",              "ar_overlay_on"),
    ("ar overlay off",               "ar_overlay_off"),
    ("ar overlay status",            "ar_overlay_status"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_tier7(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── phone bridge ─────────────────────────────────────────────────


def _free_port() -> int:
    """Grab a guaranteed-free port from the OS."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture
def phone_bridge_running():
    """Start the bridge on a free port; tear down on exit."""
    from core import phone_bridge as pb
    if pb.is_running():
        pb.stop()
    port = _free_port()
    info = pb.start(host="127.0.0.1", port=port)
    assert info["ok"], info
    yield info
    pb.stop()


def test_phone_bridge_index_html(phone_bridge_running):
    url = phone_bridge_running["url"]
    with urllib.request.urlopen(url, timeout=3) as r:
        body = r.read().decode("utf-8")
    assert "AERIS Phone Bridge" in body
    assert "X-Aeris-Token" in body or "token" in body.lower()


def test_phone_bridge_skills_requires_token(phone_bridge_running):
    url = phone_bridge_running["url"] + "skills"
    req = urllib.request.Request(url)
    try:
        urllib.request.urlopen(req, timeout=3)
    except urllib.request.HTTPError as e:
        assert e.code == 401
    else:
        pytest.fail("no HTTP error raised — endpoint should require token")


def test_phone_bridge_skills_returns_list(phone_bridge_running):
    token = phone_bridge_running["token"]
    req = urllib.request.Request(phone_bridge_running["url"] + "skills",
                                 headers={"X-Aeris-Token": token})
    with urllib.request.urlopen(req, timeout=3) as r:
        body = json.loads(r.read())
    assert isinstance(body, list)
    assert len(body) > 20
    assert all("name" in row for row in body[:5])


def test_phone_bridge_fire_endpoint(phone_bridge_running):
    """POST /fire current_time → 200 with a non-empty result."""
    token = phone_bridge_running["token"]
    payload = json.dumps({"name": "current_time", "raw_text": "what's the time"}).encode("utf-8")
    req = urllib.request.Request(
        phone_bridge_running["url"] + "fire",
        data=payload,
        method="POST",
        headers={"X-Aeris-Token": token,
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3) as r:
        body = json.loads(r.read())
    assert body["ok"] is True
    assert body["name"] == "current_time"
    assert body["result"]


def test_phone_bridge_fire_unknown_skill_returns_error(phone_bridge_running):
    token = phone_bridge_running["token"]
    payload = json.dumps({"name": "definitely_not_a_real_skill_xyz",
                          "raw_text": ""}).encode("utf-8")
    req = urllib.request.Request(
        phone_bridge_running["url"] + "fire",
        data=payload, method="POST",
        headers={"X-Aeris-Token": token,
                 "Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=3)
    except urllib.request.HTTPError as e:
        body = json.loads(e.read())
        assert body["ok"] is False
        assert "not registered" in body["error"].lower()
    else:
        pytest.fail("unknown skill should have returned an error")


def test_phone_bridge_double_start_idempotent(phone_bridge_running):
    from core import phone_bridge as pb
    info = pb.start()
    assert info["ok"] is True
    assert info.get("msg", "").lower().startswith(("already", "phone"))


def test_phone_bridge_status_when_off():
    from core import phone_bridge as pb
    if pb.is_running():
        pb.stop()
    st = pb.status()
    assert st["running"] is False


# ── telemetry ────────────────────────────────────────────────────


def test_telemetry_snapshot_shape():
    from core.telemetry import snapshot
    s = snapshot(window_h=1.0)
    for key in ("gesture", "skill", "workspace", "memos",
                "journal", "kg", "faces", "window_h"):
        assert key in s


def test_telemetry_gesture_counts_handles_empty(monkeypatch):
    """When the trace log is missing, gesture_counts returns zeros, not raise."""
    import core.telemetry as tel
    monkeypatch.setattr(tel, "gesture_events", lambda window_h: [])
    g = tel.gesture_counts()
    assert g["total"] == 0
    assert g["fired"] == 0
    assert g["blocked"] == 0
    assert g["ranked"] == []


def test_telemetry_gesture_counts_ranks(monkeypatch):
    import core.telemetry as tel
    monkeypatch.setattr(tel, "gesture_events", lambda window_h: [
        {"gesture": "peace",        "status": "fired"},
        {"gesture": "peace",        "status": "fired"},
        {"gesture": "double_pinch", "status": "fired"},
        {"gesture": "peace",        "status": "blocked"},
    ])
    g = tel.gesture_counts()
    assert g["fired"] == 3
    assert g["blocked"] == 1
    assert g["ranked"][0] == ("peace", 3)
    assert g["ranked"][1] == ("double_pinch", 1)


def test_telemetry_skill_counts(monkeypatch):
    import core.telemetry as tel
    monkeypatch.setattr(tel, "gesture_events", lambda window_h: [
        {"gesture": "peace",        "status": "fired"},
        {"gesture": "peace",        "status": "blocked"},
        {"gesture": "double_pinch", "status": "fired"},
    ])
    s = tel.skill_counts()
    assert s["total"] == 2
    assert ("peace", 1) in s["ranked"]
    assert ("double_pinch", 1) in s["ranked"]


def test_telemetry_digest_skill_returns_text():
    from skills.telemetry_skill import telemetry_digest
    out = telemetry_digest({})
    assert "telemetry digest" in out.lower()
    assert "gestures" in out.lower()
    assert "memos" in out.lower()


def test_telemetry_open_skill_returns_immediately():
    import time
    from skills.telemetry_skill import open_telemetry_dashboard
    t0 = time.monotonic()
    out = open_telemetry_dashboard({})
    assert time.monotonic() - t0 < 0.5
    assert "telemetry" in out.lower()


# ── AR overlay ───────────────────────────────────────────────────


def test_ar_overlay_module_imports():
    import ui.ar_overlay as ar
    assert callable(ar.show_ar_overlay)
    assert callable(ar.hide_ar_overlay)
    assert callable(ar.is_ar_visible)


def test_ar_overlay_status_when_hidden():
    import ui.ar_overlay as ar
    ar._INSTANCE = None
    from skills.ar_overlay_skill import ar_overlay_status
    out = ar_overlay_status({})
    assert "hidden" in out.lower()


def test_ar_overlay_show_refuses_without_qapp(monkeypatch):
    """Without a QApplication, show_ar_overlay returns False (no exception)."""
    try:
        from PyQt5.QtWidgets import QApplication
    except Exception:
        pytest.skip("PyQt5 not installed")
    import ui.ar_overlay as ar
    monkeypatch.setattr(QApplication, "instance", staticmethod(lambda: None))
    ar._INSTANCE = None
    assert ar.show_ar_overlay() is False


def test_ar_overlay_skill_corner_parsing():
    from skills.ar_overlay_skill import _corner_from
    assert _corner_from("ar overlay on top right") == "top-right"
    assert _corner_from("ar overlay on bottom left") == "bottom-left"
    assert _corner_from("ar overlay on") == "top-right"   # default
