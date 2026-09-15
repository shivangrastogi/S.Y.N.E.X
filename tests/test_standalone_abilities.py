"""Standalone-ability batch: clipboard AI, doc brain v2, translator tier,
local music, transcribe (fast lane — LLM/encoder/engine all faked)."""

from __future__ import annotations

import os
import time

import pytest


class _FakeLLM:
    def __init__(self, reply="FAKE_OUT"):
        self.reply = reply
        self.calls: list[dict] = []

    def available(self):
        return True

    def generate(self, prompt, system="", max_tokens=400, temperature=0.3):
        self.calls.append({"prompt": prompt, "system": system,
                           "max_tokens": max_tokens})
        return self.reply


@pytest.fixture
def fake_llm(monkeypatch):
    import core.local_llm as ll
    f = _FakeLLM()
    monkeypatch.setattr(ll, "get", lambda: f)
    return f


# ── clipboard AI ─────────────────────────────────────────────────────── #

class TestClipboardExtract:
    def _extract(self, monkeypatch, clip, asked="clipboard extract karo"):
        from skills import clipboard_ai_skill as c
        monkeypatch.setattr(c, "_clip", lambda: clip)
        return c.clipboard_extract({"raw_text": asked})

    def test_full_extraction_clean(self, monkeypatch):
        out = self._extract(
            monkeypatch,
            "call +91 98765 43210 ya 9876543210, mail rahul@x.com, "
            "site https://a.dev/p, budget 12,500.75 aur 15%")
        assert "phones: 919876543210, 9876543210" in out or \
               "phones: +919876543210, 9876543210" in out
        assert "emails: rahul@x.com" in out
        assert "links: https://a.dev/p" in out
        # numbers must NOT leak phone fragments or bare country codes
        num_line = next(l for l in out.splitlines() if l.startswith("numbers"))
        assert "12,500.75" in num_line and "15%" in num_line
        assert "98765" not in num_line and "+91" not in num_line

    def test_phone_only_filter(self, monkeypatch):
        out = self._extract(monkeypatch, "9876543210 aur 500 rupaye",
                            asked="clipboard se phone number nikalo")
        assert "phones:" in out and "numbers:" not in out

    def test_empty_clipboard(self, monkeypatch):
        assert "khaali" in self._extract(monkeypatch, "")

    def test_nothing_found(self, monkeypatch):
        assert "nahi mila" in self._extract(monkeypatch, "sirf shabd hain yahan")


class TestClipboardLLM:
    def test_summarize_uses_clean_llm(self, monkeypatch, fake_llm):
        from skills import clipboard_ai_skill as c
        monkeypatch.setattr(c, "_clip", lambda: "lambi baat " * 30)
        out = c.clipboard_summarize({})
        assert out == "FAKE_OUT"
        assert "Summarise" in fake_llm.calls[0]["system"]
        assert "sir" not in fake_llm.calls[0]["system"]   # no persona leak

    def test_rewrite_and_bullets_prompts(self, monkeypatch, fake_llm):
        from skills import clipboard_ai_skill as c
        monkeypatch.setattr(c, "_clip", lambda: "kuch text")
        c.clipboard_rewrite({})
        c.clipboard_bullets({})
        systems = [x["system"] for x in fake_llm.calls]
        assert any("professional" in s for s in systems)
        assert any("bullet" in s for s in systems)

    def test_empty_clip_never_calls_llm(self, monkeypatch, fake_llm):
        from skills import clipboard_ai_skill as c
        monkeypatch.setattr(c, "_clip", lambda: "")
        assert "khaali" in c.clipboard_summarize({})
        assert fake_llm.calls == []

    def test_no_model_message(self, monkeypatch):
        import core.local_llm as ll

        class _Absent(_FakeLLM):
            def available(self):
                return False
        monkeypatch.setattr(ll, "get", lambda: _Absent())
        from skills import clipboard_ai_skill as c
        monkeypatch.setattr(c, "_clip", lambda: "text hai")
        assert "gguf" in c.clipboard_summarize({})


# ── translator standalone tier ───────────────────────────────────────── #

class TestTranslatorLocalTier:
    def test_via_llm_clean_prompt_and_backend(self, fake_llm):
        from core.translator import translate
        out, backend = translate("namaste duniya", "english")
        assert (out, backend) == ("FAKE_OUT", "llm")
        call = fake_llm.calls[0]
        assert "precise translator" in call["system"]
        assert "ONLY the translation" in call["system"]
        assert "namaste duniya" in call["prompt"]

    def test_token_budget_scales_with_text(self, fake_llm):
        from core.translator import translate
        translate("x" * 800, "hindi")
        assert fake_llm.calls[0]["max_tokens"] >= 400


# ── doc brain v2 ─────────────────────────────────────────────────────── #

class TestDocBrain:
    def test_docx_extraction(self, tmp_path):
        import docx
        from core.doc_index import _read_text
        p = tmp_path / "m.docx"
        d = docx.Document()
        d.add_paragraph("Rahul ko 500 dena hai")
        d.save(str(p))
        assert "Rahul ko 500" in _read_text(p)

    def test_answer_synthesizes_with_citations(self, monkeypatch, fake_llm):
        from core.doc_index import DocIndex
        idx = DocIndex()
        fake_llm.reply = "Deadline 15 August hai [1]."
        monkeypatch.setattr(idx, "query", lambda q, top_k=4: [
            {"file": "C:/n/plan.md", "chunk": 0,
             "text": "Deadline: 15 August 2026", "score": 0.8}])
        res = idx.answer("deadline kya hai")
        assert res["answer"].startswith("Deadline 15 August")
        assert res["sources"] == ["plan.md"]
        assert "CONTEXT" in fake_llm.calls[0]["prompt"]
        assert "NOT_IN_DOCS" in fake_llm.calls[0]["system"]

    def test_answer_not_in_docs(self, monkeypatch, fake_llm):
        from core.doc_index import DocIndex
        idx = DocIndex()
        fake_llm.reply = "NOT_IN_DOCS"
        monkeypatch.setattr(idx, "query", lambda q, top_k=4: [
            {"file": "a.md", "chunk": 0, "text": "kuch aur", "score": 0.5}])
        assert idx.answer("q")["answer"] is None

    def test_answer_old_index_format_asks_rebuild(self, monkeypatch, fake_llm):
        from core.doc_index import DocIndex
        idx = DocIndex()
        monkeypatch.setattr(idx, "query", lambda q, top_k=4: [
            {"file": "a.md", "chunk": 0, "score": 0.6}])   # no text key
        res = idx.answer("q")
        assert res["answer"] is None and "dobara index" in res["why"]
        assert fake_llm.calls == []

    def test_answer_low_score_filtered(self, monkeypatch, fake_llm):
        from core.doc_index import DocIndex
        idx = DocIndex()
        monkeypatch.setattr(idx, "query", lambda q, top_k=4: [
            {"file": "a.md", "chunk": 0, "text": "x", "score": 0.1}])
        assert idx.answer("q")["answer"] is None

    def test_summarize_file_head_tail_for_long_docs(self, tmp_path, fake_llm):
        from core.doc_index import summarize_file
        p = tmp_path / "big.txt"
        p.write_text("A" * 6000 + "MID" + "Z" * 6000, encoding="utf-8")
        out = summarize_file(str(p))
        assert out == "FAKE_OUT"
        prompt = fake_llm.calls[0]["prompt"]
        assert "AAA" in prompt and "ZZZ" in prompt and "MID" not in prompt

    def test_summarize_missing_file(self, fake_llm):
        from core.doc_index import summarize_file
        assert summarize_file("C:/nahi/hai.txt") is None


# ── local music ──────────────────────────────────────────────────────── #

@pytest.fixture
def music_lib(tmp_path):
    from core.local_music import LocalMusicLibrary
    mdir = tmp_path / "Music"
    mdir.mkdir()
    for name in ("Kesariya - Brahmastra.mp3", "Kabhi Jo Badal Barse.m4a",
                 "lecture_recording.wav", "notes.txt"):
        (mdir / name).write_bytes(b"x")
    lib = LocalMusicLibrary(index_path=str(tmp_path / "idx.json"))
    lib.build([str(mdir)])
    return lib


class TestLocalMusic:
    def test_index_skips_non_audio(self, music_lib):
        assert music_lib.stats()["tracks"] == 3

    def test_exact_substring_match(self, music_lib):
        assert music_lib.find("kesariya")[0]["name"].startswith("Kesariya")

    def test_partial_token_match(self, music_lib):
        assert any("Badal" in h["name"] for h in music_lib.find("badal barse"))

    def test_prefix_fuzzy(self, music_lib):
        assert music_lib.find("kesari")[0]["name"].startswith("Kesariya")

    def test_play_uses_default_player(self, music_lib, monkeypatch):
        opened = []
        monkeypatch.setattr(os, "startfile", lambda p: opened.append(p),
                            raising=False)
        ok, msg = music_lib.play("kesariya")
        assert ok and opened and opened[0].endswith(".mp3")
        assert "Kesariya" in msg

    def test_play_miss_message(self, music_lib):
        ok, msg = music_lib.play("zzz nahi hai")
        assert not ok and "nahi mila" in msg

    def test_play_random(self, music_lib, monkeypatch):
        opened = []
        monkeypatch.setattr(os, "startfile", lambda p: opened.append(p),
                            raising=False)
        ok, msg = music_lib.play_random()
        assert ok and msg.startswith("Shuffle:") and opened

    def test_persistence_roundtrip(self, music_lib, tmp_path):
        from core.local_music import LocalMusicLibrary
        again = LocalMusicLibrary(index_path=str(tmp_path / "idx.json"))
        assert again.stats()["tracks"] == 3


# ── transcribe skill ─────────────────────────────────────────────────── #

class TestTranscribe:
    def test_no_path_prompts(self):
        from skills.transcribe_skill import transcribe_file
        assert "Path do" in transcribe_file({"raw_text": "audio transcribe karo"})

    def test_missing_file(self):
        from skills.transcribe_skill import transcribe_file
        out = transcribe_file(
            {"raw_text": r"audio transcribe karo C:\nahi\hai.wav"})
        assert "nahi mili" in out

    def test_engine_unavailable_degrades_clearly(self, tmp_path, monkeypatch):
        wav = tmp_path / "a.wav"
        wav.write_bytes(b"RIFF")
        import core.stt_whisper as sw

        class _Eng:
            def is_available(self):
                return False
        monkeypatch.setattr(sw, "get_whisper_engine", lambda: _Eng())
        from skills.transcribe_skill import transcribe_file
        out = transcribe_file({"raw_text": f"audio transcribe karo {wav}"})
        assert "faster-whisper" in out and "offline" in out.lower()

    def test_success_short_transcript_spoken_inline(self, tmp_path, monkeypatch):
        wav = tmp_path / "a.wav"
        wav.write_bytes(b"RIFF")
        import core.stt_whisper as sw

        class _Eng:
            def is_available(self):
                return True

            def transcribe(self, path):
                return "meeting kal subah dus baje hai"
        monkeypatch.setattr(sw, "get_whisper_engine", lambda: _Eng())
        from skills.transcribe_skill import transcribe_file
        out = transcribe_file({"raw_text": f"audio transcribe karo {wav}"})
        assert out.startswith("meeting kal subah")
        assert "data/notes" not in out          # short → no note file
