"""Tier 6 — cross-machine sync, document QA, text translator.

Side-effect-safe:
  * sync tests round-trip through tmp_path (never touch real data/).
  * doc_index tests use tiny synthetic text files + stub the encoder so
    the real ~120 MB model isn't loaded for each test.
  * translator tests stub both LLM and argos paths to avoid HTTP.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "sync_export", "sync_import", "sync_list", "sync_default_path",
    "doc_index_folder", "doc_query", "doc_status", "doc_clear",
    "translate_to", "translate_clipboard", "translate_status",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("sync export",                "sync_export"),
    ("backup aeris",               "sync_export"),
    ("sync import",                "sync_import"),
    ("sync list",                  "sync_list"),
    ("sync default path",          "sync_default_path"),
    ("index folder",               "doc_index_folder"),
    ("index my documents",         "doc_index_folder"),
    ("doc query",                  "doc_query"),
    ("search docs for",            "doc_query"),
    ("doc status",                 "doc_status"),
    ("doc clear",                  "doc_clear"),
    ("translate to",               "translate_to"),
    ("translate clipboard",        "translate_clipboard"),
    ("translate status",           "translate_status"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_tier6(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── sync ─────────────────────────────────────────────────────────


def test_sync_default_path_includes_aeris_sync():
    from core.sync import default_export_path
    p = default_export_path()
    assert "aeris_sync_" in p
    assert p.endswith(".zip")


def test_sync_export_no_files_when_empty(monkeypatch, tmp_path):
    import core.sync as sync
    # Point _DATA at an empty tmp dir → nothing to pack.
    monkeypatch.setattr(sync, "_DATA", tmp_path / "empty")
    (tmp_path / "empty").mkdir()
    target = tmp_path / "out.zip"
    info = sync.export_snapshot(str(target))
    assert info["ok"] is False
    assert info["files"] == 0
    assert "nahi mili" in info["msg"].lower() or "no" in info["msg"].lower()


def test_sync_export_packs_files(monkeypatch, tmp_path):
    import core.sync as sync
    data = tmp_path / "data"
    data.mkdir()
    (data / "settings.json").write_text('{"x": 1}', encoding="utf-8")
    (data / "custom_gestures.json").write_text('{"peace": []}', encoding="utf-8")
    (data / "notes").mkdir()
    (data / "notes" / "journal.md").write_text("hello\n", encoding="utf-8")
    monkeypatch.setattr(sync, "_DATA", data)
    target = tmp_path / "out.zip"
    info = sync.export_snapshot(str(target))
    assert info["ok"] is True
    assert info["files"] == 3
    assert target.exists()
    # ZIP contains the three files at the expected arcnames.
    with zipfile.ZipFile(target) as zf:
        names = set(zf.namelist())
    assert "settings.json" in names
    assert "custom_gestures.json" in names
    assert "notes/journal.md" in names


def test_sync_import_restores_and_backs_up(monkeypatch, tmp_path):
    import core.sync as sync
    data = tmp_path / "data"
    data.mkdir()
    # Existing settings to be backed up.
    (data / "settings.json").write_text('{"old": true}', encoding="utf-8")
    monkeypatch.setattr(sync, "_DATA", data)
    # Build a ZIP that overwrites settings.json.
    src = tmp_path / "in.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("settings.json", '{"new": true}')
        zf.writestr("knowledge_graph.json", "[]")
    info = sync.import_snapshot(str(src))
    assert info["ok"] is True
    assert info["restored"] == 2
    assert info["backed_up"] == 1
    # Settings.json should now contain the new payload.
    assert json.loads((data / "settings.json").read_text(encoding="utf-8")) == {"new": True}
    # A .bak file should have been created.
    bak_files = list(data.glob("settings.json.bak-*"))
    assert bak_files, "expected backup file"


def test_sync_import_rejects_traversal(monkeypatch, tmp_path):
    import core.sync as sync
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(sync, "_DATA", data)
    src = tmp_path / "evil.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("../../oops.json", '{"escape": true}')
        zf.writestr("/etc/safe.json", "{}")
        zf.writestr("good.json", '{"x": 1}')
    info = sync.import_snapshot(str(src))
    # Only 'good.json' should have been restored; traversal entries skipped.
    assert info["restored"] == 1
    assert info["skipped"] == 2


def test_sync_import_missing_file():
    from core.sync import import_snapshot
    info = import_snapshot("nonexistent_sync_xyz.zip")
    assert info["ok"] is False
    assert "nahi mila" in info["msg"].lower() or "not" in info["msg"].lower()


# ── doc_index ────────────────────────────────────────────────────


class _StubEncoder:
    """Deterministic 8-d embedder — score boosts when the query token
    appears in the chunk (simple bag-of-words-style projection)."""
    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
        import math
        rows = []
        for t in texts:
            v = [0.0] * 8
            t_lo = (t or "").lower()
            # Each "dimension" lights up for a specific keyword family.
            keywords = ["budget", "report", "meeting", "project",
                        "deadline", "client", "feature", "bug"]
            for i, kw in enumerate(keywords):
                if kw in t_lo:
                    v[i] = 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            rows.append([x / n for x in v])
        # Return as a numpy-like list-of-lists (DocIndex wraps in np.asarray).
        return rows


def _doc_index_with_files(monkeypatch, tmp_path, files: dict[str, str]):
    """Helper — build a synthetic folder + index it with the stub encoder."""
    import core.doc_index as di
    folder = tmp_path / "docs"
    folder.mkdir()
    for name, body in files.items():
        (folder / name).write_text(body, encoding="utf-8")
    monkeypatch.setattr(di, "_INDEX_PATH", tmp_path / "doc_index.pkl")
    monkeypatch.setattr(di, "_META_PATH",  tmp_path / "doc_index_meta.json")
    monkeypatch.setattr(di, "_get_encoder", lambda: _StubEncoder())
    di._DEFAULT = None
    idx = di.get_doc_index()
    info = idx.build(str(folder))
    return idx, info


def test_doc_index_build_basic(monkeypatch, tmp_path):
    files = {
        "a.md": "Q1 budget report draft for the client meeting on Monday." * 4,
        "b.md": "Bug list and feature roadmap for the next sprint." * 4,
    }
    idx, info = _doc_index_with_files(monkeypatch, tmp_path, files)
    assert info["ok"] is True
    assert info["files"] == 2
    assert info["chunks"] >= 2


def test_doc_query_returns_top_hit(monkeypatch, tmp_path):
    files = {
        "budget.md": ("budget budget budget Q1 report meeting " * 30),
        "bugs.md":   ("bug fix feature project " * 30),
    }
    idx, _ = _doc_index_with_files(monkeypatch, tmp_path, files)
    hits = idx.query("budget", top_k=3)
    assert hits
    # Top hit should be from budget.md
    assert "budget.md" in hits[0]["file"]


def test_doc_query_empty_index_returns_nothing(monkeypatch, tmp_path):
    import core.doc_index as di
    monkeypatch.setattr(di, "_INDEX_PATH", tmp_path / "doc_index.pkl")
    monkeypatch.setattr(di, "_META_PATH",  tmp_path / "doc_index_meta.json")
    monkeypatch.setattr(di, "_get_encoder", lambda: _StubEncoder())
    di._DEFAULT = None
    idx = di.get_doc_index()
    assert idx.query("anything") == []


def test_doc_clear_resets(monkeypatch, tmp_path):
    files = {"a.md": "budget budget budget " * 30}
    idx, _ = _doc_index_with_files(monkeypatch, tmp_path, files)
    assert idx.stats()["chunks"] > 0
    n = idx.clear()
    assert n > 0
    assert idx.stats()["chunks"] == 0


def test_doc_index_skips_huge_files(monkeypatch, tmp_path):
    """Files over the 256 KB cap should be skipped."""
    import core.doc_index as di
    folder = tmp_path / "docs"
    folder.mkdir()
    huge = folder / "big.txt"
    huge.write_bytes(b"a" * (300 * 1024))
    (folder / "small.md").write_text("budget meeting " * 50, encoding="utf-8")
    monkeypatch.setattr(di, "_INDEX_PATH", tmp_path / "doc_index.pkl")
    monkeypatch.setattr(di, "_META_PATH",  tmp_path / "doc_index_meta.json")
    monkeypatch.setattr(di, "_get_encoder", lambda: _StubEncoder())
    di._DEFAULT = None
    idx = di.get_doc_index()
    info = idx.build(str(folder))
    assert info["ok"] is True
    # Only the small file contributed.
    files = {m["file"] for m in idx._meta}
    assert all("big.txt" not in f for f in files)


def test_doc_skill_status_when_empty(monkeypatch, tmp_path):
    import core.doc_index as di
    monkeypatch.setattr(di, "_INDEX_PATH", tmp_path / "doc_index.pkl")
    monkeypatch.setattr(di, "_META_PATH", tmp_path / "doc_index_meta.json")
    di._DEFAULT = None
    from skills.doc_qa_skill import doc_status
    out = doc_status({})
    assert "khaali" in out.lower() or "empty" in out.lower()


def test_doc_skill_query_needs_text():
    from skills.doc_qa_skill import doc_query
    out = doc_query({"raw_text": "doc query"})
    assert "query do" in out.lower() or "?" in out or "search" in out.lower()


# ── translator ───────────────────────────────────────────────────


def test_translator_lang_code_aliases():
    from core.translator import lang_code
    assert lang_code("French") == "fr"
    assert lang_code("hindi") == "hi"
    assert lang_code("japanese") == "ja"
    assert lang_code("fr") == "fr"
    assert lang_code("") == "en"
    # Unknown → safe default
    assert lang_code("klingon") == "en"


def test_translator_list_languages_non_empty():
    from core.translator import list_languages
    langs = list_languages()
    assert "english" in langs
    assert "hindi" in langs
    assert len(langs) >= 12


def test_translator_parse_basic():
    from skills.translator_skill import _parse
    body, lang = _parse("translate hello to french")
    assert body == "hello"
    assert lang == "french"
    body, lang = _parse("translate this whole thing into japanese")
    assert "whole thing" in body
    assert lang == "japanese"


def test_translator_uses_llm_when_available(monkeypatch):
    import core.translator as tr
    monkeypatch.setattr(tr, "_via_llm", lambda t, l: f"LLM-translated: {t}")
    out, backend = tr.translate("hello", "french")
    assert backend == "llm"
    assert "hello" in out


def test_translator_falls_back_to_argos(monkeypatch):
    import core.translator as tr
    monkeypatch.setattr(tr, "_via_llm", lambda t, l: None)
    monkeypatch.setattr(tr, "_via_argos", lambda t, l: f"ARGOS: {t}")
    out, backend = tr.translate("hello", "french")
    assert backend == "argos"
    assert "ARGOS" in out


def test_translator_final_fallback_returns_browser_url(monkeypatch):
    import core.translator as tr
    monkeypatch.setattr(tr, "_via_llm", lambda t, l: None)
    monkeypatch.setattr(tr, "_via_argos", lambda t, l: None)
    monkeypatch.setattr("webbrowser.open", lambda url: True)
    out, backend = tr.translate("hello", "french")
    assert backend == "google_url"
    assert "translate.google.com" in out


def test_translator_skill_empty_body():
    from skills.translator_skill import translate_to
    out = translate_to({"raw_text": "translate to french"})
    assert "Format" in out or "format" in out.lower()


def test_translator_skill_tags_backend(monkeypatch):
    import core.translator as tr
    monkeypatch.setattr(tr, "translate",
                        lambda t, l: (f"BONJOUR {t}", "llm"))
    from skills.translator_skill import translate_to
    out = translate_to({"raw_text": "translate hello to french"})
    assert out.startswith("[llm]")
    assert "BONJOUR" in out
