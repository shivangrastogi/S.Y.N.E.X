"""Agentic-layer upgrade: tool selection, embedded JSON turns, park/resume
persistence, AI-assisted review, retrain-due initiative (fast lane)."""

from __future__ import annotations

import json

import pytest

from core.tool_select import select_tools
from core.llm_chat import LLMChat


MANIFEST = [
    {"name": "open_app", "description": "Launch a desktop application", "args": ["app_name"]},
    {"name": "close_app", "description": "Kill a running application", "args": ["app_name"]},
    {"name": "take_screenshot", "description": "Capture screen to file", "args": []},
    {"name": "image_to_phone", "description": "Send an image to the phone via bridge", "args": ["path"]},
    {"name": "play_music", "description": "Play a song locally", "args": []},
    {"name": "get_weather", "description": "Current weather report", "args": []},
    {"name": "create_note", "description": "Save a text note", "args": ["content"]},
    {"name": "web_search", "description": "Search the web", "args": ["query"]},
    {"name": "lock_screen", "description": "Lock the workstation", "args": []},
    {"name": "volume_up", "description": "Increase system volume", "args": []},
    {"name": "battery_status", "description": "Battery percentage", "args": []},
    {"name": "set_reminder", "description": "Schedule a reminder", "args": ["message", "time"]},
    {"name": "compose_email", "description": "Draft an email", "args": ["to"]},
    {"name": "find_file", "description": "Find a file on disk", "args": ["query"]},
]


class TestToolSelect:
    def test_brain_top_intents_rank_first(self):
        picked = select_tools("chrome kholo", MANIFEST,
                              top_intents=[("open_app", 0.9)], k=5)
        assert picked[0]["name"] == "open_app"

    def test_secondary_step_tool_found_by_token_overlap(self):
        picked = select_tools(
            "screenshot le aur phone pe bhej do", MANIFEST,
            top_intents=[("take_screenshot", 0.8)], k=6)
        names = {t["name"] for t in picked}
        assert "take_screenshot" in names
        assert "image_to_phone" in names       # "phone" overlap, no intent hit

    def test_hinglish_hint_bridges_vocabulary(self):
        picked = select_tools("gana bajao yaar", MANIFEST, k=4)
        assert any(t["name"] == "play_music" for t in picked)

    def test_k_cap_and_small_manifest_passthrough(self):
        assert len(select_tools("kuch bhi", MANIFEST, k=3)) <= 3
        small = MANIFEST[:4]
        assert select_tools("anything", small, k=12) == small

    def test_no_match_falls_back_to_manifest_head(self):
        picked = select_tools("zzz qqq xxx", MANIFEST, k=3)
        assert picked == MANIFEST[:3]


# ── embedded JSON turns ─────────────────────────────────────────────── #

class _FakeLocal:
    def __init__(self, reply='{"tool": "final", "reply": "done"}'):
        self.reply = reply
        self.calls: list = []

    def available(self):
        return True

    def chat_json(self, messages, max_tokens=160):
        self.calls.append(messages)
        return self.reply


class _Act:
    def __init__(self, name, args):
        self.kind, self.name, self.args, self.reply = "tool", name, args, None


class _Step:
    def __init__(self, name, args, obs):
        self.action = _Act(name, args)
        self.observation = obs
        self.blocked = False


class TestEmbeddedAgentTurns:
    @pytest.fixture
    def fake_llm(self, monkeypatch):
        import core.local_llm as ll
        fake = _FakeLocal()
        monkeypatch.setattr(ll, "get", lambda: fake)
        return fake

    def test_agent_step_prompt_contains_goal_and_tools(self, fake_llm):
        out = LLMChat()._embedded_agent_step(
            "screenshot lo", [], MANIFEST[:3], {"name": "Shivang"})
        assert out == '{"tool": "final", "reply": "done"}'
        msgs = fake_llm.calls[0]
        assert "take_screenshot" in msgs[0]["content"]
        assert msgs[1]["content"] == "GOAL: screenshot lo"

    def test_scratchpad_replay_truncates_and_caps(self, fake_llm):
        steps = [_Step("web_search", {"query": "x"}, "R" * 1000)
                 for _ in range(10)]
        LLMChat()._embedded_agent_step("goal", steps, MANIFEST[:2], {})
        msgs = fake_llm.calls[0]
        replayed = [m for m in msgs if m["content"].startswith("OBSERVATION")]
        assert len(replayed) == LLMChat._EMBEDDED_MAX_STEPS
        assert all(len(m["content"]) <= LLMChat._EMBEDDED_OBS_CHARS + 20
                   for m in replayed)

    def test_tool_reply_single_shot(self, fake_llm):
        out = LLMChat()._embedded_tool_reply(
            "chrome kholo", {"name": "Shivang"}, MANIFEST[:3])
        assert out is not None
        msgs = fake_llm.calls[0]
        assert msgs[-1] == {"role": "user", "content": "chrome kholo"}

    def test_kill_switch_disables_embedded_agent(self, monkeypatch, fake_llm):
        import core.settings as settings
        monkeypatch.setattr(
            settings, "get",
            lambda k, d=None: False if k == "agent_embedded" else d)
        monkeypatch.setattr(LLMChat, "_backend", staticmethod(lambda: "embedded"))
        out = LLMChat().agent_step("goal", [], MANIFEST[:2], {})
        assert out is None and fake_llm.calls == []

    def test_agent_step_routes_to_embedded_when_enabled(self, monkeypatch,
                                                        fake_llm):
        import core.settings as settings
        monkeypatch.setattr(settings, "get", lambda k, d=None: d)
        monkeypatch.setattr(LLMChat, "_backend", staticmethod(lambda: "embedded"))
        out = LLMChat().agent_step("goal", [], MANIFEST[:2], {})
        assert out == '{"tool": "final", "reply": "done"}'


class TestChatJson:
    def test_grammar_kwarg_then_typeerror_fallback(self, monkeypatch):
        from core.local_llm import LocalLLM

        calls = []

        class _FakeLlama:
            def create_chat_completion(self, **kw):
                calls.append(kw)
                if "response_format" in kw:
                    raise TypeError("response_format unsupported")
                return {"choices": [{"message": {"content": '{"ok": 1}'}}]}

        l = LocalLLM()
        monkeypatch.setattr(l, "_ensure_loaded", lambda: _FakeLlama())
        assert l.chat_json([{"role": "user", "content": "hi"}]) == '{"ok": 1}'
        assert "response_format" in calls[0] and "response_format" not in calls[1]

    def test_no_model_returns_none(self, monkeypatch):
        from core.local_llm import LocalLLM
        l = LocalLLM()
        monkeypatch.setattr(l, "_ensure_loaded", lambda: None)
        assert l.chat_json([]) is None


# ── park → persist → resume round trip (main_engine._park_agent_run logic) ─ #

class TestParkResumeRoundTrip:
    def test_parked_direct_run_survives_and_resumes_approved(self, tmp_path):
        from core import goal_system
        from core.agent_orchestrator import (AgentAction, AgentResult,
                                             AgentStep)
        store = goal_system.GoalStore(str(tmp_path / "goals.json"))

        parked = AgentResult(
            reply="'lock_screen' karne se pehle confirmation chahiye.",
            steps=[AgentStep(
                action=AgentAction(kind="tool", name="lock_screen", args={}),
                observation="AWAITING CONFIRMATION: 'lock_screen'.",
                blocked=True, park_reason="need_user")],
            stopped_reason="blocked", block_reason="need_user")

        # …what _park_agent_run does:
        g = goal_system.Goal(text="screen lock karke music band karo",
                             source="agent")
        g.scratchpad = goal_system.steps_to_scratch(parked.steps)
        store.add(g)
        store.park(g, parked.block_reason, ask=parked.reply)

        # …what Step 2h does on "haan":
        pending = store.awaiting_confirmation(within_s=300)
        assert pending is not None and pending.ask == parked.reply

        seen = {}

        class _Orch:
            def run(self, text, prior_steps=None, approved=None):
                seen["prior"] = prior_steps
                seen["approved"] = approved
                return AgentResult(reply="Lock ho gaya, sir.",
                                   stopped_reason="final")

        res = goal_system.advance(store, pending, _Orch(), approve_last=True)
        assert res.reply == "Lock ho gaya, sir."
        assert seen["approved"] == {"lock_screen"}
        assert seen["prior"][0].action.name == "lock_screen"
        assert store.get(g.id).state == "done"

    def test_repeat_parked_run_replaces_older_twin(self, tmp_path):
        # main_engine._park_agent_run drops older agent-parked twins of the
        # same text so repeated blocked commands never pile up zombie goals.
        from core import goal_system
        store = goal_system.GoalStore(str(tmp_path / "goals.json"))

        def park_run(text, ask):
            for old in store.by_state("blocked"):
                if old.source == "agent" and old.text == text:
                    store.drop(old)
            g = goal_system.Goal(text=text, source="agent")
            store.add(g)
            store.park(g, "need_user", ask=ask)
            return g

        park_run("lock karo", "pehla ask")
        g2 = park_run("lock karo", "doosra ask")
        blocked = store.by_state("blocked")
        assert len(blocked) == 1 and blocked[0].id == g2.id
        assert blocked[0].ask == "doosra ask"


# ── AI-assisted review ──────────────────────────────────────────────── #

class TestAiSuggest:
    def _patch_llm(self, monkeypatch, reply, available=True):
        import core.local_llm as ll
        fake = _FakeLocal(reply=reply)
        if not available:
            fake.available = lambda: False
        monkeypatch.setattr(ll, "get", lambda: fake)

    def test_match_verdict(self, monkeypatch):
        from core.learning_loop import ai_suggest
        self._patch_llm(monkeypatch, '{"match": true, "why": "same request"}')
        verdict, why = ai_suggest("chrome chala", "open_app", ["open chrome"])
        assert verdict is True and why == "same request"

    def test_offline_gives_no_verdict(self, monkeypatch):
        from core.learning_loop import ai_suggest
        self._patch_llm(monkeypatch, "", available=False)
        verdict, why = ai_suggest("x", "open_app", [])
        assert verdict is None and "offline" in why

    def test_garbage_output_gives_no_verdict(self, monkeypatch):
        from core.learning_loop import ai_suggest
        self._patch_llm(monkeypatch, "not json at all")
        verdict, _ = ai_suggest("x", "open_app", [])
        assert verdict is None


# ── retrain-due initiative ──────────────────────────────────────────── #

class TestRetrainInitiative:
    @pytest.fixture
    def recommended(self, monkeypatch, tmp_path):
        import core.brain_health as bh
        r = bh.HealthReport(window_days=7)
        r.retrain_recommended = True
        r.new_since_train = 21
        monkeypatch.setattr(bh, "collect", lambda **k: r)
        monkeypatch.setattr(bh, "CARD_DIR", str(tmp_path))
        monkeypatch.setattr(bh, "_NUDGE_STAMP", str(tmp_path / "stamp"))
        return bh

    def test_offers_once_then_throttles(self, recommended):
        first = recommended.initiative_candidates()
        assert len(first) == 1
        ini = first[0]
        assert ini.kind == "retrain_due" and "21" in ini.text
        # Salience lands in the OFFER band, never autonomous act.
        assert 0.12 <= ini.score() < 0.28
        assert recommended.initiative_candidates() == []   # 24h throttle

    def test_silent_when_not_recommended(self, monkeypatch, tmp_path):
        import core.brain_health as bh
        r = bh.HealthReport(window_days=7)
        monkeypatch.setattr(bh, "collect", lambda **k: r)
        monkeypatch.setattr(bh, "_NUDGE_STAMP", str(tmp_path / "stamp"))
        assert bh.initiative_candidates() == []
