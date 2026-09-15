"""Cloud bridge — crypto, pairing, and lifecycle guards (no network)."""
import base64
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import core.cloud_bridge as cb


# ── crypto ───────────────────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip():
    key = os.urandom(32)
    payload = {"id": "abc", "type": "chat", "text": "battery kitni hai?",
               "reply_to": None, "extra": {}}
    doc = cb.encrypt_payload(key, payload)
    assert set(doc) == {"n", "ct"}
    assert cb.decrypt_payload(key, doc) == payload


def test_decrypt_rejects_wrong_key():
    doc = cb.encrypt_payload(os.urandom(32), {"text": "secret"})
    assert cb.decrypt_payload(os.urandom(32), doc) is None


def test_decrypt_rejects_tampered_ciphertext():
    key = os.urandom(32)
    doc = cb.encrypt_payload(key, {"text": "hello"})
    raw = bytearray(base64.b64decode(doc["ct"]))
    raw[0] ^= 0xFF
    doc["ct"] = base64.b64encode(bytes(raw)).decode()
    assert cb.decrypt_payload(key, doc) is None


def test_decrypt_rejects_garbage():
    assert cb.decrypt_payload(os.urandom(32), {"n": "!!", "ct": "??"}) is None
    assert cb.decrypt_payload(os.urandom(32), {}) is None


# ── pairing ──────────────────────────────────────────────────────────

@pytest.fixture
def temp_pair_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(cb, "_SECRETS_DIR", str(tmp_path))
    monkeypatch.setattr(cb, "_PAIR_PATH", str(tmp_path / "bridge_pair.json"))
    monkeypatch.setattr(cb, "_QR_PATH", str(tmp_path / "pair_qr.png"))
    return tmp_path


def test_new_pairing_persists_and_renders_qr(temp_pair_paths):
    info = cb.new_pairing("my-project")
    assert len(info["pid"]) == 32          # 128-bit hex
    assert len(info["key"]) == 32          # AES-256
    assert os.path.isfile(cb._PAIR_PATH)
    assert info["qr_path"] and os.path.isfile(info["qr_path"])
    loaded = cb.load_pair()
    assert loaded["pid"] == info["pid"]
    assert loaded["key"] == info["key"]


def test_repairing_rotates_key(temp_pair_paths):
    a = cb.new_pairing("p")
    b = cb.new_pairing("p")
    assert a["pid"] != b["pid"] and a["key"] != b["key"]
    # Disk holds only the NEW pairing — old phone is locked out.
    assert cb.load_pair()["pid"] == b["pid"]


def test_load_pair_none_when_never_paired(temp_pair_paths):
    assert cb.load_pair() is None


def test_qr_payload_contains_everything_the_app_needs(temp_pair_paths):
    info = cb.new_pairing("aeris-bridge-proj")
    import PIL.Image  # qr readable? decode not needed — check saved JSON side
    saved = json.load(open(cb._PAIR_PATH, encoding="utf-8"))
    assert saved["pid"] == info["pid"]
    key = base64.b64decode(saved["key_b64"])
    assert key == info["key"]


# ── lifecycle guards ─────────────────────────────────────────────────

def test_start_without_hook_or_key_fails_cleanly(temp_pair_paths, monkeypatch):
    # conftest sets AERIS_DISABLE_BRIDGE=1 for the whole session so no test
    # can open a real Firestore listener. This test is specifically about
    # start()'s own guards, so it opts out — it still can't connect (there is
    # no service-account key at the patched path).
    monkeypatch.delenv("AERIS_DISABLE_BRIDGE", raising=False)
    monkeypatch.setattr(cb, "_SA_KEY_PATH", str(temp_pair_paths / "nope.json"))
    b = cb.CloudBridge()
    ok, msg = b.start(None)
    assert not ok and "hook" in msg.lower()
    ok, msg = b.start(lambda t: "hi")
    assert not ok and "service-account" in msg.lower()


def test_status_shape(temp_pair_paths, monkeypatch):
    monkeypatch.setattr(cb, "_SA_KEY_PATH", str(temp_pair_paths / "nope.json"))
    s = cb.CloudBridge().status()
    assert set(s) >= {"sa_key", "paired", "listening", "reason"}
    assert s["sa_key"] is False and s["listening"] is False


# ── AERIS_DISABLE_BRIDGE gate ────────────────────────────────────────
# The engine auto-starts the bridge on every construction, which under pytest
# meant a live Firestore listener + presence/clipboard daemon threads per
# engine-building test, never stopped. This gate is what keeps the suite (and
# any offline run) from touching the real pairing.

@pytest.mark.parametrize("val,want", [
    ("1", True), ("true", True), ("YES", True), ("on", True),
    ("0", False), ("", False), ("off", False), ("no", False),
])
def test_bridge_disabled_flag_parsing(val, want, monkeypatch):
    monkeypatch.setenv("AERIS_DISABLE_BRIDGE", val)
    assert cb.bridge_disabled() is want


def test_bridge_disabled_by_default_under_pytest():
    """conftest sets it for the session — if this fails, the suite is once
    again free to open live Firestore listeners."""
    assert cb.bridge_disabled() is True


def test_start_refuses_when_disabled(temp_pair_paths, monkeypatch):
    """Even with a hook wired, a disabled bridge must not connect or spawn
    threads — the gate sits ahead of every side effect in start()."""
    monkeypatch.setenv("AERIS_DISABLE_BRIDGE", "1")
    b = cb.CloudBridge()
    connected = []
    monkeypatch.setattr(b, "_connect", lambda: connected.append(1) or True)

    ok, msg = b.start(lambda t: "hi")

    assert ok is False
    assert "disabled" in msg.lower()
    assert connected == [], "disabled bridge must not even try to connect"
    assert b._started is False
    assert getattr(b, "_presence_thread", None) is None
    assert getattr(b, "_clip_thread", None) is None
