"""Fact bridge — high-precision fact extraction from conversation.

Precision matters more than recall here: a wrong "fact" pollutes the
knowledge graph silently. These tests pin both what MUST extract and,
just as importantly, what must NOT.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.fact_bridge import extract_facts, learn_from


# ── positive frames ──────────────────────────────────────────────────

def test_likes_hinglish():
    assert ("user", "likes", "blue color") in extract_facts(
        "yaar mujhe blue color bohot pasand hai")


def test_likes_english():
    assert ("user", "likes", "lo-fi music") in extract_facts(
        "i really love lo-fi music")


def test_favourite_english():
    assert ("user", "favourite editor", "vscode") in extract_facts(
        "my favourite editor is vscode")


def test_favourite_hinglish():
    assert ("user", "favourite game", "valorant") in extract_facts(
        "mera favourite game valorant hai")


def test_works_at():
    assert ("user", "works at", "sehatup") in extract_facts(
        "i work at sehatup")


def test_learning_hinglish():
    assert ("user", "learning", "flutter") in extract_facts(
        "main flutter seekh raha hoon")


def test_birthday():
    assert ("user", "birthday", "12 march") in extract_facts(
        "my birthday is on 12 march")


# ── precision guards: must NOT extract ───────────────────────────────

def test_negation_rejected():
    assert extract_facts("mujhe gajar pasand nahi hai") == []
    assert extract_facts("i don't like mondays") == []


def test_pronoun_objects_rejected():
    assert extract_facts("i like it") == []
    assert extract_facts("i love this") == []
    assert extract_facts("i love you") == []


def test_runon_objects_rejected():
    assert extract_facts(
        "i love the way the rain sounds when i am trying to sleep at "
        "night with the window open") == []


def test_plain_chat_extracts_nothing():
    for t in ("yaar aaj bohot thak gaya hoon",
              "kya lagta hai AI duniya badal degi",
              "battery status",
              "open notepad"):
        assert extract_facts(t) == []


# ── storage path (KG mocked — never touches the real graph) ─────────

def test_learn_from_stores_via_kg(monkeypatch):
    stored = []

    class _FakeKG:
        def add_triple(self, s, p, o):
            stored.append((s, p, o))

    import core.fact_bridge as fb
    import core.kg_memory as kgm
    monkeypatch.setattr(kgm, "get_kg", lambda: _FakeKG())
    n = fb.learn_from("mera favourite game valorant hai")
    assert n == 1
    assert stored == [("user", "favourite game", "valorant")]


def test_learn_from_noop_on_chat(monkeypatch):
    import core.kg_memory as kgm
    monkeypatch.setattr(kgm, "get_kg",
                        lambda: (_ for _ in ()).throw(AssertionError(
                            "KG must not be touched when nothing extracted")))
    assert learn_from("yaar aaj mood off hai") == 0
