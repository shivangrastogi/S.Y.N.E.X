"""Local file intelligence — folder stats, large-file finder, read-aloud."""

from __future__ import annotations

import os

import pytest

from core import file_tools as ft


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "a.txt").write_text("hello " * 100, encoding="utf-8")
    (tmp_path / "b.md").write_text("# note\nkuch text", encoding="utf-8")
    (tmp_path / "big.log").write_bytes(b"x" * 500_000)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "e.py").write_text("print(1)", encoding="utf-8")
    return tmp_path


class TestResolveFolder:
    def test_explicit_windows_path(self):
        assert ft.resolve_folder(r"is folder me kya hai C:\Notes\x") == \
               r"C:\Notes\x"

    def test_keyword_folder(self):
        out = ft.resolve_folder("downloads me kitni files hain")
        assert out and out.lower().endswith("downloads")

    def test_none_when_no_folder(self):
        assert ft.resolve_folder("kuch bhi random") is None


class TestFolderStats:
    def test_counts_and_types(self, tree):
        out = ft.folder_stats(str(tree))
        assert "4 files" in out
        assert ".txt" in out and "total" in out

    def test_missing_folder(self):
        assert "nahi mila" in ft.folder_stats("C:/does/not/exist/xyz")

    def test_empty_folder(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert "khaali" in ft.folder_stats(str(empty))


class TestLargeFiles:
    def test_sorted_by_size(self, tree):
        out = ft.find_large_files(str(tree), 3)
        lines = out.splitlines()[1:]        # drop header
        assert "big.log" in lines[0]        # 500KB is biggest
        assert len(lines) == 3

    def test_missing_folder(self):
        assert "nahi mila" in ft.find_large_files("C:/nope/zzz")

    def test_cap_respected(self, tree):
        # asking for more than exist just returns all
        out = ft.find_large_files(str(tree), 50)
        assert out.count("\n") <= 4 + 1


class TestReadFileText:
    def test_reads_text_file(self, tree):
        res = ft.read_file_text(str(tree / "b.md"))
        assert res is not None
        content, truncated = res
        assert "kuch text" in content and truncated is False

    def test_truncates_long(self, tmp_path):
        p = tmp_path / "long.txt"
        p.write_text("A" * 2000, encoding="utf-8")
        content, truncated = ft.read_file_text(str(p), cap=100)
        assert truncated is True and content.endswith("…")
        assert len(content) <= 101

    def test_rejects_binary_ext(self, tmp_path):
        p = tmp_path / "x.exe"
        p.write_bytes(b"MZ\x00\x00")
        assert ft.read_file_text(str(p)) is None

    def test_missing_file(self):
        assert ft.read_file_text("C:/no/file.txt") is None

    def test_rejects_oversize(self, tmp_path):
        p = tmp_path / "huge.txt"
        p.write_bytes(b"x" * (3 * 1024 * 1024))
        assert ft.read_file_text(str(p)) is None


class TestWalkSafety:
    def test_skips_system_dirs(self, tmp_path):
        (tmp_path / "keep.txt").write_text("x", encoding="utf-8")
        ng = tmp_path / "node_modules"
        ng.mkdir()
        (ng / "junk.txt").write_text("y" * 1000, encoding="utf-8")
        files = [p.name for p, _ in ft._walk(tmp_path)]
        assert "keep.txt" in files and "junk.txt" not in files


class TestSkillWrappers:
    def test_folder_stats_skill_needs_folder(self, monkeypatch):
        from skills.file_tools_skill import folder_stats
        assert "Kis folder" in folder_stats({"raw_text": "folder stats"})

    def test_large_files_defaults_downloads(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(ft, "find_large_files",
                            lambda p, n=6: seen.setdefault("p", p))
        from skills.file_tools_skill import find_large_files
        find_large_files({"raw_text": "bade files dhundo"})
        assert seen["p"].lower().endswith("downloads")

    def test_read_aloud_truncation_note(self, tmp_path, monkeypatch):
        p = tmp_path / "n.txt"
        p.write_text("Z" * 2000, encoding="utf-8")
        from skills.file_tools_skill import read_file_aloud
        out = read_file_aloud({"raw_text": f"is file ko padho {p}"})
        assert "aur bhi hai" in out
