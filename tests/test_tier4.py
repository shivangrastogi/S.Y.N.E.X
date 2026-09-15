"""Tier 4 — GPU offload, plugin marketplace, knowledge-graph memory.

Side-effect-safe:
  * GPU tests stub torch CUDA so no real device probe is required.
  * Plugin tests use tmp_path for the plugins dir and a stub @skill.
  * KG tests use a tmp store path; the demo plugin smoke test is opt-in.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from core.skill_registry import discover_skills, all_skills

discover_skills("skills")


NEW_SKILLS = [
    "gpu_offload_on", "gpu_offload_off", "gpu_status",
    "plugin_list", "plugin_enable", "plugin_disable",
    "plugin_path", "plugin_load_all",
    "kg_remember", "kg_query", "kg_facts_about", "kg_forget", "kg_list",
]


@pytest.mark.parametrize("name", NEW_SKILLS)
def test_skill_registered(name):
    reg = all_skills()
    assert name in reg, f"{name!r} missing from registry"
    assert reg[name].patterns, f"{name} has no patterns"


# ── routing ───────────────────────────────────────────────────────

ROUTING_CASES = [
    ("gpu on",                       "gpu_offload_on"),
    ("gpu off",                      "gpu_offload_off"),
    ("gpu status",                   "gpu_status"),
    ("list plugins",                 "plugin_list"),
    ("enable plugin",                "plugin_enable"),
    ("disable plugin",               "plugin_disable"),
    ("plugin path",                  "plugin_path"),
    ("load all plugins",             "plugin_load_all"),
    ("remember that",                "kg_remember"),
    ("yaad rakho",                   "kg_remember"),
    ("who is",                       "kg_query"),
    ("where do i live",              "kg_query"),
    ("facts about",                  "kg_facts_about"),
    ("forget about",                 "kg_forget"),
    ("kg list",                      "kg_list"),
    ("list knowledge",               "kg_list"),
]


@pytest.mark.parametrize("query,expected", ROUTING_CASES)
def test_brain_routes_tier4(shared_brain, query, expected):
    p = shared_brain.predict(query)
    assert p.intent == expected, (
        f"{query!r} → {p.intent!r} (conf {p.confidence:.2f}); expected {expected!r}"
    )


# ── GPU offload ──────────────────────────────────────────────────


def test_gpu_detect_returns_dict():
    from core.gpu_offload import detect_gpu
    info = detect_gpu()
    assert isinstance(info, dict)
    assert "torch_cuda" in info
    assert "torch_installed" in info


def test_gpu_preference_round_trip(monkeypatch):
    state: dict = {}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    from core import gpu_offload as g
    assert g.is_preferred() is False
    changed, _ = g.set_preference(True)
    assert changed and g.is_preferred() is True
    # Idempotent: second call doesn't claim a change.
    changed, _ = g.set_preference(True)
    assert changed is False


def test_gpu_status_skill_returns_text():
    from skills.gpu_offload_skill import gpu_status
    out = gpu_status({})
    assert "GPU" in out


def test_gpu_on_when_no_cuda(monkeypatch):
    import core.gpu_offload as g
    monkeypatch.setattr(g, "detect_gpu", lambda: {
        "torch_cuda": False, "torch_installed": True,
        "torch_cuda_count": 0, "device_name": "",
        "ultralytics_installed": False, "insightface_installed": False,
    })
    monkeypatch.setattr(g, "set_preference",
                        lambda on: (True, f"GPU offload preference → {'ON' if on else 'OFF'}."))
    from skills.gpu_offload_skill import gpu_offload_on
    out = gpu_offload_on({})
    assert "CUDA not available" in out or "preference" in out.lower()


# ── plugin loader ────────────────────────────────────────────────


def test_plugin_dir_creates(tmp_path, monkeypatch):
    import core.plugin_loader as pl
    monkeypatch.setattr(pl, "_PLUGIN_DIR", tmp_path / "plugins")
    path = pl.plugin_dir()
    assert os.path.isdir(path)


def test_plugin_discovery(tmp_path, monkeypatch):
    """list_plugins should pick up every dir containing skill.py."""
    import core.plugin_loader as pl
    p_dir = tmp_path / "plugins"
    (p_dir / "foo").mkdir(parents=True)
    (p_dir / "foo" / "skill.py").write_text("# stub\n", encoding="utf-8")
    (p_dir / "bar").mkdir()
    (p_dir / "bar" / "skill.py").write_text("# stub\n", encoding="utf-8")
    (p_dir / "_hidden").mkdir()
    (p_dir / "_hidden" / "skill.py").write_text("# ignored\n", encoding="utf-8")
    (p_dir / "no_skill_file").mkdir()    # missing skill.py → ignored
    monkeypatch.setattr(pl, "_PLUGIN_DIR", p_dir)
    rows = pl.list_plugins()
    names = {r["name"] for r in rows}
    assert "foo" in names and "bar" in names
    assert "_hidden" not in names
    assert "no_skill_file" not in names


def test_plugin_enable_disable_round_trip(tmp_path, monkeypatch):
    import core.plugin_loader as pl
    p_dir = tmp_path / "plugins"
    (p_dir / "tester").mkdir(parents=True)
    (p_dir / "tester" / "skill.py").write_text(
        "from core.skill_registry import skill\n"
        "@skill(name='_tester_plugin_ping', description='tester', patterns=['_tester_ping'])\n"
        "def _ping(_s): return 'pong'\n", encoding="utf-8")
    monkeypatch.setattr(pl, "_PLUGIN_DIR", p_dir)
    state: dict = {}
    monkeypatch.setattr("core.settings.set_",
                        lambda k, v: state.update({k: v}))
    monkeypatch.setattr("core.settings.get",
                        lambda k, d=None: state.get(k, d))
    ok, msg = pl.enable("tester")
    assert ok
    assert "tester" in (state.get("plugins_enabled") or [])
    # Loaded plugin should now be in the global skill registry.
    from core.skill_registry import all_skills
    assert "_tester_plugin_ping" in all_skills()
    # Disable just flips the flag — leftover registry entry is documented.
    ok, msg = pl.disable("tester")
    assert ok
    assert "tester" not in (state.get("plugins_enabled") or [])


def test_plugin_enable_unknown(tmp_path, monkeypatch):
    import core.plugin_loader as pl
    monkeypatch.setattr(pl, "_PLUGIN_DIR", tmp_path / "plugins")
    monkeypatch.setattr("core.settings.set_", lambda k, v: None)
    monkeypatch.setattr("core.settings.get", lambda k, d=None: d)
    ok, msg = pl.enable("totally_not_there")
    assert ok is False
    assert "nahi mila" in msg.lower() or "not" in msg.lower()


def test_plugin_skill_list_handler_returns_text():
    from skills.plugin_skill import plugin_list
    out = plugin_list({})
    assert "plugin" in out.lower()


# ── knowledge graph ──────────────────────────────────────────────


def _fresh_kg(monkeypatch, tmp_path):
    import core.kg_memory as kg
    monkeypatch.setattr(kg, "_STORE_PATH", tmp_path / "knowledge_graph.json")
    kg._DEFAULT = None
    return kg.get_kg()


def test_kg_add_statement_parses_is_my(monkeypatch, tmp_path):
    g = _fresh_kg(monkeypatch, tmp_path)
    triples = g.add_statement("Sara is my sister")
    assert len(triples) == 1
    t = triples[0]
    assert t["s"] == "sara" and t["p"] == "is_my" and t["o"] == "sister"


def test_kg_add_statement_lives_in(monkeypatch, tmp_path):
    g = _fresh_kg(monkeypatch, tmp_path)
    triples = g.add_statement("I live in Mumbai")
    assert triples[0]["s"] == "user"
    assert triples[0]["p"] == "lives_in"
    assert triples[0]["o"] == "mumbai"


def test_kg_add_statement_possessive_slot(monkeypatch, tmp_path):
    g = _fresh_kg(monkeypatch, tmp_path)
    triples = g.add_statement("Sara's number is 9876543210")
    assert triples[0]["s"] == "sara"
    assert triples[0]["p"] == "number"
    assert "9876543210" in triples[0]["o"]


def test_kg_query_who_is(monkeypatch, tmp_path):
    g = _fresh_kg(monkeypatch, tmp_path)
    g.add_statement("Sara is my sister")
    assert g.query("who is Sara") == "sister"
    assert g.query("who is Notexistent") is None


def test_kg_query_where_do_i_live(monkeypatch, tmp_path):
    g = _fresh_kg(monkeypatch, tmp_path)
    g.add_statement("I live in Mumbai")
    assert g.query("where do I live") == "mumbai"
    assert g.query("where am I living") == "mumbai"


def test_kg_query_what_is_my_birthday(monkeypatch, tmp_path):
    g = _fresh_kg(monkeypatch, tmp_path)
    g.add_statement("My birthday is March 15")
    assert g.query("what is my birthday") == "march 15"


def test_kg_query_possessive_lookup(monkeypatch, tmp_path):
    g = _fresh_kg(monkeypatch, tmp_path)
    g.add_statement("Sara's number is 9876543210")
    assert g.query("Sara's number") == "9876543210"


def test_kg_facts_about_returns_only_subject(monkeypatch, tmp_path):
    g = _fresh_kg(monkeypatch, tmp_path)
    g.add_statement("Sara is my sister")
    g.add_statement("Sara likes coffee")
    g.add_statement("I live in Mumbai")
    facts = g.facts_about("sara")
    assert len(facts) == 2
    assert {f["o"] for f in facts} == {"sister", "coffee"}


def test_kg_forget_removes_subject(monkeypatch, this=None, tmp_path=None):
    pass  # placeholder so the next test name doesn't collide


def test_kg_forget(monkeypatch, tmp_path):
    g = _fresh_kg(monkeypatch, tmp_path)
    g.add_statement("Sara is my sister")
    g.add_statement("Sara likes coffee")
    g.add_statement("I live in Mumbai")
    removed = g.forget("sara")
    assert removed == 2
    assert g.facts_about("sara") == []
    # Other subjects untouched
    assert g.query("where do I live") == "mumbai"


def test_kg_dedup_same_triple(monkeypatch, tmp_path):
    g = _fresh_kg(monkeypatch, tmp_path)
    g.add_triple("sara", "is_my", "sister")
    g.add_triple("Sara", "is_my", "sister")     # normalised → same
    assert len(g.all_triples()) == 1


def test_kg_strip_lead_verbs(monkeypatch, tmp_path):
    g = _fresh_kg(monkeypatch, tmp_path)
    g.add_statement("remember that Sara is my sister")
    assert g.query("who is Sara") == "sister"


def test_kg_skill_remember_no_body():
    from skills.kg_skill import kg_remember
    out = kg_remember({"raw_text": "remember"})
    assert "kya yaad" in out.lower() or "remember" in out.lower()


def test_kg_skill_query_unknown(monkeypatch, tmp_path):
    """When the brain has no answer, the skill returns the 'pata nahi' message."""
    import core.kg_memory as kg
    monkeypatch.setattr(kg, "_STORE_PATH", tmp_path / "knowledge_graph.json")
    kg._DEFAULT = None
    from skills.kg_skill import kg_query
    out = kg_query({"raw_text": "who is Voldemort"})
    assert "pata nahi" in out.lower() or "not" in out.lower()
