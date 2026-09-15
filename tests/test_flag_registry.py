"""Flag documentation cannot silently drift (§6.36).

24 `AERIS_*` flags exist; `CLAUDE.md` documented about ten. That gap is the
ordinary fate of a hand-maintained list beside code that keeps growing, and it
matters here because these flags are how every load-free and split-mode
behaviour is switched on. A flag nobody knows about is a feature nobody uses.

So the list is discovered from the source and these tests fail when a new flag
arrives without a description, or a described flag disappears.
"""

from __future__ import annotations

import pathlib

from core.flag_registry import (
    DESCRIPTIONS, INTERNAL, discover_flags, render_markdown, stale,
    undocumented,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestDiscovery:
    def test_it_finds_the_flags_this_session_added(self):
        found = discover_flags()
        for name in ("AERIS_SPLIT_VISION", "AERIS_SPLIT_VOICE",
                     "AERIS_BRAIN_HIBERNATE_S", "AERIS_REPAIR_MEMORY",
                     "AERIS_VOICE_STREAMING"):
            assert name in found, name

    def test_it_finds_the_older_ones_too(self):
        found = discover_flags()
        for name in ("AERIS_LITE_ML", "AERIS_SPLIT_BRAIN",
                     "AERIS_IDLE_UNLOAD_S", "AERIS_CAMERA_IDLE_S"):
            assert name in found, name

    def test_each_flag_records_where_it_is_read(self):
        f = discover_flags()["AERIS_SPLIT_VISION"]
        assert f.sites and all(":" in s for s in f.sites)
        assert any("remote_gesture_engine" in s for s in f.sites)

    def test_it_does_not_scan_its_own_descriptions(self):
        """Every DESCRIPTIONS key is a string literal in `flag_registry.py`.
        If that file were scanned, every flag would be rediscovered from its
        own description — and `stale()` could never fire, which is the one
        thing it exists to do."""
        for f in discover_flags().values():
            assert not any("flag_registry" in s for s in f.sites), f.name

    def test_a_removed_flag_would_be_reported_stale(self):
        """Proves the guard can fail — a description with no source site."""
        fake = dict(discover_flags())
        fake.pop("AERIS_LITE_ML", None)
        assert "AERIS_LITE_ML" in stale(fake)


class TestTheGuard:
    def test_every_flag_in_the_source_has_a_description(self):
        missing = undocumented()
        assert not missing, (
            f"{len(missing)} flag(s) have no description: {missing}. "
            f"Add them to DESCRIPTIONS in core/flag_registry.py — an "
            f"undocumented flag is a feature nobody can find.")

    def test_no_description_outlives_its_flag(self):
        gone = stale()
        assert not gone, (
            f"described but not found in the source: {gone}. Remove them, or "
            f"the doc is now lying about what exists.")

    def test_internal_flags_are_excluded_not_forgotten(self):
        """Tooling knobs are deliberately kept out of the user-facing table,
        which is different from being overlooked."""
        found = discover_flags()
        for name in INTERNAL:
            if name in found:
                assert found[name].internal
                assert name not in DESCRIPTIONS

    def test_every_description_has_a_default_and_a_section(self):
        for name, entry in DESCRIPTIONS.items():
            assert len(entry) == 3, name
            desc, default, section = entry
            assert desc.strip() and default.strip(), name
            assert section in ("Split mode", "Load", "Devices", "Behaviour"), name


class TestGeneratedDoc:
    def test_the_committed_doc_is_current(self):
        """`docs/FLAGS.md` is generated; a stale copy is worse than none,
        because it reads as authoritative."""
        path = ROOT / "docs" / "FLAGS.md"
        assert path.exists(), "run: python gen_flags_doc.py"
        on_disk = path.read_text(encoding="utf-8")
        assert on_disk == render_markdown(), (
            "docs/FLAGS.md is out of date — run: python gen_flags_doc.py")

    def test_the_doc_says_it_is_generated(self):
        assert "do not edit by hand" in render_markdown().lower()

    def test_every_documented_flag_appears_in_the_rendered_table(self):
        out = render_markdown()
        for name in DESCRIPTIONS:
            assert f"`{name}`" in out, name

    def test_the_doc_records_where_each_flag_is_read(self):
        out = render_markdown()
        assert "## Where each is read" in out
        assert "AERIS_SPLIT_VOICE" in out.split("## Where each is read", 1)[1]
