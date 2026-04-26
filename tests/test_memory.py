"""User memory tests — uses tmp_memory_path so no real data is touched."""

import json

from core.memory import UserMemory


def test_store_name_english(tmp_memory_path):
    m = UserMemory(tmp_memory_path)
    ack = m.detect_and_store("hello my name is shivang")
    assert ack is not None
    assert "Shivang" in ack
    assert m.get("name") == "Shivang"


def test_store_name_hinglish(tmp_memory_path):
    m = UserMemory(tmp_memory_path)
    ack = m.detect_and_store("main hoon shaurya")
    assert ack is not None
    assert m.get("name") == "Shaurya"


def test_store_location(tmp_memory_path):
    m = UserMemory(tmp_memory_path)
    m.detect_and_store("i live in delhi please")
    assert m.get("location") == "Delhi"


def test_store_employer(tmp_memory_path):
    m = UserMemory(tmp_memory_path)
    m.detect_and_store("i work at google")
    assert m.get("employer") == "Google"


def test_store_favorite_english_order(tmp_memory_path):
    m = UserMemory(tmp_memory_path)
    m.detect_and_store("my favourite browser is chrome")
    assert m.get("favorite_browser") == "Chrome"


def test_store_favorite_hinglish_order(tmp_memory_path):
    """Hinglish puts 'hai' at the end: 'mera favourite gaana X hai'."""
    m = UserMemory(tmp_memory_path)
    m.detect_and_store("mera favourite gaana shape of you hai")
    assert m.get("favorite_gaana") == "Shape Of You"


def test_remember_note(tmp_memory_path):
    m = UserMemory(tmp_memory_path)
    m.detect_and_store("remember that i need to buy milk on tuesdays")
    notes = m.all_notes()
    assert len(notes) == 1
    assert "milk" in notes[0]


def test_persistence_round_trip(tmp_memory_path):
    """Facts written to disk should reload cleanly into a new instance."""
    m1 = UserMemory(tmp_memory_path)
    m1.set("name", "Shivang")
    m1.set("location", "Delhi")
    m2 = UserMemory(tmp_memory_path)
    assert m2.get("name") == "Shivang"
    assert m2.get("location") == "Delhi"


def test_recall_english(tmp_memory_path):
    m = UserMemory(tmp_memory_path)
    m.set("name", "Shivang")
    r = m.detect_and_recall("what's my name")
    assert r is not None and "Shivang" in r


def test_recall_hindi_alias_naam(tmp_memory_path):
    m = UserMemory(tmp_memory_path)
    m.set("name", "Shivang")
    r = m.detect_and_recall("mera naam kya hai")
    assert r is not None and "Shivang" in r


def test_recall_hindi_alias_ghar(tmp_memory_path):
    m = UserMemory(tmp_memory_path)
    m.set("location", "Delhi")
    r = m.detect_and_recall("mera ghar kya hai")
    assert r is not None and "Delhi" in r


def test_recall_unknown_key_polite_failure(tmp_memory_path):
    m = UserMemory(tmp_memory_path)
    r = m.detect_and_recall("what's my pet")
    assert r is not None
    assert "pata nahi" in r.lower() or "don't know" in r.lower()


def test_no_memory_pattern_returns_none(tmp_memory_path):
    m = UserMemory(tmp_memory_path)
    assert m.detect_and_store("weather batao") is None
    assert m.detect_and_recall("weather batao") is None


def test_what_do_you_know_about_me(tmp_memory_path):
    m = UserMemory(tmp_memory_path)
    m.set("name", "Shivang")
    m.set("location", "Delhi")
    r = m.detect_and_recall("what do you know about me")
    assert r is not None
    assert "Shivang" in r
    assert "Delhi" in r
