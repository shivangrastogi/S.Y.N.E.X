"""Top-level orchestrator for AERIS / Jarvis.

The brain pipeline assembled here uses every module shipped in C1–C8:

    STT → process_text → TTS

`process_text` is a pure function of (text, internal state) → response_text.
The audio I/O lives only in `run()`. This makes the brain testable without
mics or speakers — just call `engine.process_text("chrome kholo")` and get
a string back.

Pipeline order inside `process_text`:

    0. If state is mid slot-fill or mid disambig → handle that turn first
    1. If we're waiting on feedback for a prior execution and the user said
       "galat"/"wrong" within one turn → record correction reward
    2. If text matches a memory-setting pattern → save it, ack
    3. If text is a cancel keyword (no state) → polite "nothing to cancel"
    4. Sentiment classify
    5. Brain predict (raw, no internal threshold — we use the bandit's)
    6. If confidence ≥ per-intent learned threshold:
         a. close-call?  → ask disambig
         b. otherwise   → extract entities, run state machine, execute
    7. Else → LLM chit-chat fallback (if Ollama up) or queue for review
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import settings as _settings
from core.brain import JarvisBrain
from core.conversation import ConversationHistory
from core.dialogue_context import (
    CHAT_GATE_CONFIDENCE, ContextResolver, DialogueState, analogy_rewrite,
    rewrite_pronoun, say_again_reply,
)
from core.disambiguator import Disambiguator
from core.entity_extractor import EntityExtractor
from core.executor import ActionExecutor
from core.feedback import FeedbackStore
from core.llm_chat import LLMChat
from core.memory import UserMemory
from core.sentiment import SentimentAnalyzer
from core.skill_registry import discover_skills, tools_manifest
from core.state_manager import StateManager
from core.tool_router import ToolRouter, parse_tool_response
from core.agent_orchestrator import AgentOrchestrator
from core.utterance_parser import find_best_interpretation, split_into_segments

log = logging.getLogger(__name__)


def _unload_idle_llm() -> bool:
    """Idle-unload hook: release the local Qwen model (a 1 GB gguf).

    `LocalLLM.maybe_unload_idle()` has existed — documented in that module's
    own header — with zero callers, so once the LLM answered a single chat
    turn its weights stayed resident for the life of the process. `peek()`
    rather than `get()`: never construct an LLM just to ask whether one needs
    unloading. The LLM keeps its own last-used clock, so it declines if it is
    still warm.
    """
    try:
        from core import local_llm
        llm = local_llm.peek()
        return bool(llm and llm.maybe_unload_idle())
    except Exception as e:
        log.debug("[engine] llm idle-unload skipped: %s", e)
        return False

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_CANCEL_KEYWORDS = {
    "cancel", "cancel karo", "ruko", "rok do", "rehne do",
    "nahi karna", "nevermind", "never mind", "stop",
}

_CORRECTION_KEYWORDS = {
    "galat", "galat hai", "yeh galat hai", "wrong", "that's wrong",
    "undo", "wapas", "galti", "no that's wrong",
}


def _norm(t: str) -> str:
    return (t or "").strip().lower()


def _is_cancel(text: str) -> bool:
    return _norm(text) in _CANCEL_KEYWORDS


def _is_correction(text: str) -> bool:
    return _norm(text) in _CORRECTION_KEYWORDS


class JarvisMainEngine:
    def __init__(self, stt=None, tts=None, *,
                 memory_path: Optional[str] = None,
                 feedback_db_path: Optional[str] = None,
                 memory_passphrase: Optional[str] = None,
                 enable_scheduler: bool = True,
                 enable_tool_calls: bool = True,
                 enable_agent: bool = True,
                 verbose: bool = True,
                 lazy: bool = False):
        if verbose:
            print(f"Initialising {_settings.assistant_name()} v3.4 (brain + plugins + tool calling)...")

        self._stt = stt
        self._tts = tts
        self._memory_path = memory_path
        self._feedback_db_path = feedback_db_path
        self._memory_passphrase = memory_passphrase
        self._enable_scheduler = enable_scheduler
        self._enable_tool_calls = enable_tool_calls
        self._enable_agent = enable_agent
        self._verbose = verbose

        self.brain = None
        self.entity_extractor = None
        self.sentiment = None
        self.memory = None
        self.history = None
        self.disambiguator = None
        self.feedback = None
        self.llm = None
        self.state = None
        self.executor = None
        self.scheduler = None
        self.tool_router = None
        self.agent = None
        # Lite-ML boot (core/lite_ml.py) — resolved in setup_iter; declared
        # here so the attribute exists for engines that never run setup_iter.
        self._lite_ml = False
        self._deferred_ml_warmed = False

        # Pending-feedback tracker: id of the most recent executed utterance
        # awaiting a one-turn-window correction signal.
        self._pending_utterance_id: Optional[int] = None
        # Parked destructive action awaiting "haan"/"cancel" (one turn):
        # (intent, slots) — see core/confirm_gate.py.
        self._pending_confirm: Optional[tuple[str, dict]] = None
        # Parked proactive OFFER awaiting "haan" (one turn) — e.g. a
        # mode_suggest nudge. Non-destructive: "haan" runs it, anything else
        # just drops it and processes the new input normally.
        self._pending_offer: Optional[tuple[str, dict]] = None
        # process_text is now reachable from TWO threads (GUI brain worker
        # + cloud-bridge phone commands). The state machine / dialogue /
        # feedback stack is single-track, so serialize whole turns.
        # RLock because the confirm-gate abort path re-enters process_text.
        self._pt_lock = threading.RLock()
        # Side-channel for the GUI's per-reply "which skill fired" chip:
        # the metadata of the most recent dispatch, set synchronously at the
        # dispatch seam so the UI can read it right after process_text().
        self.last_dispatch: Optional[dict] = None
        self.is_running = True

        # Dialogue context — the working memory BETWEEN turns that lets
        # "isko band karo" / "aur delhi ka?" resolve against the previous
        # command. Lightweight (no models), so built eagerly even in lazy
        # mode; applies identically to typed and spoken input.
        self.dialogue = DialogueState()
        self.context = ContextResolver(self.dialogue)

        # In-session self-correction (P3): when a phrasing misses and the
        # user's immediate rephrase works, remember phrase→intent so the
        # failed phrasing works from then on. Pure logic, no models.
        #
        # OFF unless AERIS_REPAIR_MEMORY=1, following the house rule for
        # anything that changes which skill fires — this one also persists to
        # disk, so it stays opt-in until you've watched what it learns
        # (`data/repair_memory.json` is plain JSON, and `/repair` shows it).
        self.repair = None
        self._turn_from_alias = False
        if os.environ.get("AERIS_REPAIR_MEMORY", "").strip() in ("1", "true", "yes"):
            try:
                from core.repair_memory import RepairMemory, set_active
                self.repair = RepairMemory()
                set_active(self.repair)     # so the inspection skill can see it
                log.info("[repair] self-correction on (%d learned phrasings)",
                         len(self.repair))
            except Exception as e:
                log.warning("[repair] could not start: %s", e)

        # Default path: build everything synchronously (used by main.py and
        # the test suite). The GUI worker opts into `lazy=True` and drives
        # `setup_iter()` itself so it can paint progress between chunks.
        if not lazy:
            for _ in self.setup_iter():
                pass
            if verbose:
                print(f"{_settings.assistant_name()} is online.")

    # ------------------------------------------------------------------ #
    #  Chunked initialization                                              #
    # ------------------------------------------------------------------ #

    def setup_iter(self):
        """Generator that builds the brain stack in small chunks.

        Yields ``(log_type, label, pct)`` BEFORE each chunk runs so a GUI
        worker can paint progress and process pending events between chunks.
        """
        # Phase 0 — Discover plugin skills BEFORE the brain builds its index,
        # so plugin patterns participate in k-NN classification.
        yield ("SYS", "Discovering plugin skills", 4)
        # Serialize every clipboard touch in this process before any skill can
        # run one. Cheap (no import of pyperclip if it isn't installed) and it
        # closes a real 0xC0000374 heap-corruption path — see
        # core/clipboard_lock.py for the mechanism.
        try:
            from core.clipboard_lock import install as _install_clip_lock
            _install_clip_lock()
        except Exception as e:
            log.debug("[engine] clipboard lock install skipped: %s", e)
        n_skills = discover_skills("skills")
        if self._verbose and n_skills:
            print(f"  Loaded {n_skills} plugin skills.")

        self.brain = JarvisBrain(lazy=True)

        # AERIS_LITE_ML — boot with NO model weights in RAM. The tiered
        # router answers exact-match / arithmetic / anchor utterances with
        # string work alone, and pulls the encoder + neural head in on the
        # first utterance that misses them (core/lite_ml.py).
        from core.lite_ml import lite_ml_enabled
        self._lite_ml = lite_ml_enabled()

        if self._lite_ml:
            yield ("NLU", "Building fast-tier router (lite)", 12)
            self.brain.prepare_fast_tiers()
            # Everything boot is skipping gets switched on the instant the
            # encoder actually loads, so lite and eager converge.
            self.brain.add_ml_loaded_hook(self._warm_deferred_ml)
            log.info("[engine] LITE ML boot — encoder/neural/index deferred "
                     "to first heavy utterance")
        else:
            yield ("NLU", "Loading sentence encoder", 12)
            self.brain.load_encoder()

            yield ("NLU", "Loading neural intent model", 22)
            self.brain.load_neural_model()

            yield ("NLU", "Loading intent index", 32)
            self.brain.build_or_load_index()

        # Entity extractor split into 3 sub-phases — the spaCy NER load alone
        # is the slowest single step in the entire boot (5-15s on cold disk).
        # Sub-yields keep the progress bar visibly advancing through it.
        yield ("NLU", "Loading entities gazetteer", 38)
        self.entity_extractor = EntityExtractor(
            entities_path=os.path.join(_ROOT, "data", "entities.json"),
            intents_path=os.path.join(_ROOT, "data", "intents.json"),
            lazy=True,
        )
        self.entity_extractor._load_gazetteer()

        yield ("NLU", "Loading intents file", 44)
        self.entity_extractor._load_intents()

        if self._lite_ml:
            # spaCy loads on the first utterance whose slot-filling actually
            # reaches the NER layer (EntityExtractor._ensure_spacy), or with
            # the encoder via the ml-loaded hook — whichever comes first. The
            # gazetteer + regex layers, which handle most commands, are
            # already live above.
            self.entity_extractor.defer_spacy = True
        else:
            yield ("NLU", "Loading spaCy NER model", 50)
            self.entity_extractor._init_spacy()

        yield ("NLU", "Preparing chat gate", 54)
        # Encoder-based chat-vs-command gate. Reuses the brain's sentence
        # encoder (no extra model). First-ever boot pays ~20 s to embed
        # the corpora + fit the head; every later boot loads a cached pkl
        # in milliseconds. On any failure the keyword heuristic remains
        # the fallback inside is_chatty_hybrid().
        try:
            from core import chat_gate as _chat_gate
            from core.encoder_lock import ENCODER_LOCK as _ENC_LOCK
            _enc = self.brain.classifier

            def _locked_encode(texts):
                # Shared encoder — serialize against the semantic-memory
                # embed thread + brain predict, else concurrent torch
                # forwards corrupt the heap (see core/encoder_lock.py).
                with _ENC_LOCK:
                    return _enc.encoder.encode(
                        texts, normalize_embeddings=True,
                        show_progress_bar=False)

            _chat_gate.configure(_locked_encode)
            if not self._lite_ml:
                _chat_gate.ensure_ready()
            # Lite mode: fitting/loading the head needs the encoder, so it is
            # deferred to `_warm_deferred_ml` (hooked above). Until then
            # `chat_probability()` returns None and is_chatty_hybrid() uses
            # its keyword fallback — its documented degrade path.
        except Exception as _cg_err:
            log.warning("chat gate init failed (keyword fallback): %s", _cg_err)

        yield ("NLU", "Loading sentiment analyzer", 58)
        self.sentiment = SentimentAnalyzer()

        yield ("MEM", "Loading user memory", 65)
        self.memory = UserMemory(
            self._memory_path or os.path.join(_ROOT, "data", "user_memory.json"),
            passphrase=self._memory_passphrase,
        )
        # Memory Fabric (Q1·M1): one ranked recall surface over user memory +
        # KG + semantic memory. Wire the LIVE singletons so reads/writes stay
        # consistent. Never let this block boot.
        try:
            from core import memory_fabric, semantic_memory
            from core.kg_memory import get_kg
            # Hand semantic memory THIS brain's encoder rather than letting it
            # load a second one. Its only previous reuse path walked Qt
            # widgets, so every headless context (split-brain child, --text,
            # tests) silently ran two encoders. A lambda, not the object, so
            # nothing is loaded now and an idle-unload/reload is picked up.
            semantic_memory.get().set_encoder_provider(
                lambda: self.brain.classifier.encoder if self.brain else None)
            # Goals are deliberately NOT passed: the fabric's lazy default
            # provider returns `goal_system.get_goal_store()`, the same module
            # singleton this engine uses everywhere else, so reads stay
            # consistent without forcing the goal store to load at boot.
            memory_fabric.configure(
                semantic=semantic_memory.get(),
                kg=get_kg(),
                user_memory=self.memory,
            )
        except Exception as e:
            log.debug("[engine] memory fabric wiring skipped: %s", e)
        self.history = ConversationHistory(max_turns=8)
        # Publish the active history so plugin skills (repeat_last, recall)
        # can read recent turns without a direct engine reference.
        try:
            from core.conversation import set_active as _set_active_history
            _set_active_history(self.history)
        except Exception:
            pass
        self.disambiguator = Disambiguator()

        yield ("MEM", "Attaching feedback DB", 72)
        self.feedback = FeedbackStore(self._feedback_db_path
                                      or os.path.join(_ROOT, "data", "feedback_log.sqlite"))

        yield ("ACT", "Connecting LLM client", 78)
        self.llm = LLMChat()

        yield ("SYS", "Wiring scheduler + state machine + executor", 90)
        self.scheduler = self._build_scheduler() if self._enable_scheduler else None
        self.state = StateManager()
        self.executor = ActionExecutor(scheduler=self.scheduler)
        self.tool_router = ToolRouter(executor=self.executor, memory=self.memory)
        if self._enable_agent:
            self.agent = self._build_agent()

        yield ("SYS", "Wiring cloud bridge", 96)
        # Phone ↔ laptop bridge: wire the brain hook and auto-start when a
        # pairing + service-account key already exist. Fully silent no-op
        # otherwise — AERIS works identically without the bridge.
        try:
            from core.cloud_bridge import get_bridge
            _b = get_bridge()
            # Phone-origin texts carry their source so the continuity
            # registry knows which body the user is at; the router speaks
            # through the engine's own voice when the laptop is the target.
            _b.set_engine_hook(
                lambda t: self.process_text(t, source="phone"))
            try:
                from core.continuity import get_router
                get_router().speak_fn = self._speak
            except Exception:
                pass
            if _settings.get("bridge_enabled", True):
                _ok, _msg = _b.start(None)
                if _ok:
                    log.info("cloud bridge auto-started")
        except Exception as _bridge_err:
            log.debug("cloud bridge not started: %s", _bridge_err)

        # Give the weights back when nobody's talking to AERIS. Without this
        # the brain held ~800 MB from its first hard utterance until exit —
        # try_unload_idle() existed but only the GUI's memory-PRESSURE
        # callback ever called it, i.e. only once the machine was already
        # struggling (and that path can't see a split-brain child at all).
        # Starting it here covers the in-process engine and the child brain
        # with one implementation. AERIS_IDLE_UNLOAD_S=0 turns it off.
        # The brain only owns the encoder + neural head. spaCy (~220 MB) and
        # the local Qwen LLM (a 1 GB gguf) are loaded on demand and were never
        # released — which is why RSS stayed ~495 MB after one hard utterance
        # even with the brain's own weights dropped. Sweep them on the same
        # tick. Both hooks are keyed off the brain being idle, which is a
        # sound proxy: entity extraction and LLM chat both happen downstream
        # of a predict, so no predicts means neither has run either.
        try:
            self.brain.add_idle_unload_hook(self._unload_idle_spacy)
            self.brain.add_idle_unload_hook(_unload_idle_llm)
            self.brain.start_idle_unloader()
        except Exception as e:
            log.debug("[engine] idle-unloader not started: %s", e)

        yield ("SYS", "All modules nominal · brain ready", 100)

    def _unload_idle_spacy(self) -> bool:
        """Idle-unload hook: drop spaCy when the brain has gone quiet."""
        ee = self.entity_extractor
        if ee is None or ee.nlp is None:
            return False
        return ee.unload_spacy()

    def _warm_deferred_ml(self) -> None:
        """Switch on the encoder-dependent extras lite boot skipped.

        Called by JarvisBrain the first time the heavy models land in RAM
        (see ``JarvisBrain.add_ml_loaded_hook``). Idempotent — both steps are
        no-ops once done — and best-effort: a failure here just means the
        existing degrade paths (gazetteer-only NER, keyword chat gate) stay
        in force, exactly as they already do when spaCy isn't installed.
        """
        if getattr(self, "_deferred_ml_warmed", False):
            return
        self._deferred_ml_warmed = True
        t0 = time.monotonic()
        try:
            if self.entity_extractor is not None:
                # `_ensure_spacy` is the same one-shot the NER layer uses, so
                # whichever path gets here first wins and the other no-ops.
                self.entity_extractor._ensure_spacy()
        except Exception as e:
            log.warning("[engine] deferred spaCy load failed: %s", e)
        try:
            from core import chat_gate as _chat_gate
            _chat_gate.ensure_ready()
        except Exception as e:
            log.warning("[engine] deferred chat-gate warm failed: %s", e)
        log.info("[engine] deferred ML extras warmed in %.1fs",
                 time.monotonic() - t0)

    def _build_scheduler(self):
        """Create the reminder scheduler if APScheduler is available."""
        try:
            from core.scheduler import ReminderScheduler
        except ImportError:
            return None

        def _on_fire(message: str) -> None:
            if message == "__consolidate__":
                self._run_consolidation()
                return
            if message == "__initiative__":
                self._surface_initiatives()
                self._schedule_next_initiative()
                return
            if message == "__eval__":
                # P5: nightly golden-task run → report card (L4-unlock ka gate).
                try:
                    from core.eval_harness import run_nightly
                    run_nightly()
                except Exception as e:
                    log.debug("[engine] eval run failed: %s", e)
                # Continual-learning: nightly brain-health card alongside it,
                # so the trend survives even if the CLI is never run.
                try:
                    from core.brain_health import collect, write_card
                    write_card(collect(window_days=7))
                except Exception as e:
                    log.debug("[engine] nightly brain-health failed: %s", e)
                self._schedule_next_eval()
                return
            self._speak(f"Reminder, sir: {message}")

        try:
            sched = ReminderScheduler(_on_fire)
        except ImportError:
            return None
        # Q1·M1 / learning-loop 2: line up tonight's memory consolidation.
        try:
            from core.memory_consolidation import schedule_nightly
            schedule_nightly(sched)
        except Exception as e:
            log.debug("[engine] nightly consolidation scheduling skipped: %s", e)
        # Q2·M4: a proactive heartbeat — periodically let the Initiative Engine
        # surface anything worth saying (a due goal, low battery, a break). The
        # engine's quiet-hours + anti-nag budget keep it from being chatty.
        self.scheduler = sched          # so _schedule_next_initiative sees it
        self._schedule_next_initiative()
        self._schedule_next_eval()
        return sched

    _INITIATIVE_EVERY_S = 15 * 60       # heartbeat cadence

    def _schedule_next_initiative(self) -> None:
        if self.scheduler is None:
            return
        try:
            from datetime import datetime, timedelta
            fire_at = datetime.now() + timedelta(seconds=self._INITIATIVE_EVERY_S)
            self.scheduler.schedule("__initiative__", fire_at)
        except Exception as e:
            log.debug("[engine] initiative scheduling skipped: %s", e)

    def _schedule_next_eval(self) -> None:
        """Nightly golden-task eval at 04:11 (consolidation ke baad)."""
        if self.scheduler is None:
            return
        try:
            from datetime import datetime, timedelta
            now = datetime.now()
            fire = now.replace(hour=4, minute=11, second=0, microsecond=0)
            if fire <= now:
                fire += timedelta(days=1)
            self.scheduler.schedule("__eval__", fire)
        except Exception as e:
            log.debug("[engine] eval scheduling skipped: %s", e)

    def _surface_initiatives(self) -> None:
        """Tick the Initiative Engine and act on whatever it decides is worth
        surfacing now — speak a notification, or actually resume a due goal.
        Best-effort: never let a surfacing hiccup disturb the engine."""
        try:
            from core.initiative_engine import get_engine
            from core import initiative_dispatch, goal_system
            surfaced = get_engine().tick()
            if not surfaced:
                return
            store = goal_system.get_goal_store()
            agent = getattr(self, "agent", None)
            for ini in surfaced:
                res = initiative_dispatch.dispatch(
                    ini, goals=store, orchestrator=agent)
                if res.text:
                    # Continuity: proactive speech goes to the ACTIVE body —
                    # phone gets an E2E reply.route envelope, laptop speaks
                    # locally. Any routing hiccup falls back to laptop TTS.
                    try:
                        from core.continuity import get_router
                        _r = get_router()
                        if _r.speak_fn is None:
                            _r.speak_fn = self._speak
                        _r.route_reply(res.text, reason=ini.kind)
                    except Exception:
                        self._speak(res.text)
                    # A mode-suggest OFFER parks a one-turn "haan" → activate.
                    if getattr(ini, "kind", "") == "mode_suggest":
                        sid = getattr(ini, "source_id", "") or ""
                        mode = sid.split(":", 1)[1] if ":" in sid else ""
                        if mode:
                            self._pending_offer = (
                                "activate_mode", {"raw_text": mode})
                    # P4: await the user's reaction to this kind of nudge.
                    try:
                        from core.openness import get_store as _op
                        _op().surfaced(ini.kind)
                    except Exception:
                        pass
        except Exception as e:
            log.debug("[engine] initiative surfacing skipped: %s", e)
        # P4: reactions that never came settle as "ignored" on the heartbeat.
        try:
            from core.openness import get_store as _op
            _op().settle()
        except Exception:
            pass
        # Sentient-Partner P6: let the Cognition Loop raise its own thought.
        try:
            self._surface_cognition()
        except Exception as e:
            log.debug("[engine] cognition surfacing skipped: %s", e)

    def _surface_cognition(self) -> None:
        """Sentient-Partner P6 surface: on the proactive heartbeat, let the
        Cognition Loop reason over the live Context Bus and, if it forms a
        worthwhile thought, speak it. Actionable thoughts park a one-turn "haan"
        (reusing the Anticipation surface's _pending_suggestion). Real sessions
        only; the loop is itself rate-limited, mood- and quiet-hours-aware."""
        if self._tts == "SKIP":
            return
        from core import cognition, context_bus
        bus = context_bus.get()
        # Feed a fresh battery reading — unplugged only, so a low-battery nudge
        # never fires while charging (and desktops with no battery stay silent).
        try:
            import psutil
            b = psutil.sensors_battery()
            bus.set_battery(int(b.percent) if (b and not b.power_plugged) else None)
        except Exception:
            pass
        # Next *imminent* reminder (<=30 min) → the bus, so cognition can give a
        # timely heads-up. Internal heartbeat jobs (message "__…") are skipped.
        try:
            import datetime as _dt
            sched = getattr(self, "scheduler", None)
            nxt = None
            if sched is not None:
                for r in sched.list_upcoming():
                    if not str(r.message).startswith("__"):
                        nxt = r
                        break
            if nxt is not None:
                mins = max(0, int((nxt.fire_at - _dt.datetime.now()).total_seconds() // 60))
                bus.set_next_event(f"{nxt.message} ({mins} min me)" if mins <= 30 else None)
            else:
                bus.set_next_event(None)
        except Exception:
            pass
        thought = cognition.get().reflect(bus.snapshot())
        if thought is None:
            return
        # Dedup: never proactively re-offer a command Anticipation just offered
        # (both draw from anticipation.suggest — this stops a double heads-up).
        if thought.command and self._recently_offered(thought.command):
            return
        # L3 "you just think it, it does": at a trusted autonomy level, a very
        # confident + safe (AUTO-tier) habit is DONE silently and reported, not
        # asked. Everything else is spoken as an offer.
        if (thought.command and getattr(thought, "action", "offer") == "do"
                and self._autodo_allowed(bus)):
            self._auto_do(thought)
            return
        # Not auto-doing → speak it as an offer. A confident "do" thought we
        # chose NOT to auto-run (autonomy below 3) is re-phrased as a question,
        # so AERIS never claims to have done something it only offered.
        msg = thought.message
        if thought.command and getattr(thought, "action", "offer") == "do":
            msg = f"{thought.command} karoon?"
        self._speak_proactive(msg, reason=f"cognition:{thought.kind}")
        # Actionable → park it so a "haan" replays the command next turn.
        if thought.command:
            self._pending_suggestion = thought.command

    def _speak_proactive(self, msg: str, *, reason: str) -> None:
        """Speak an unsolicited line through the continuity-aware router (phone
        gets an E2E envelope; laptop speaks locally); fall back to local TTS."""
        try:
            from core.continuity import get_router
            _r = get_router()
            if _r.speak_fn is None:
                _r.speak_fn = self._speak
            _r.route_reply(msg, reason=reason)
        except Exception:
            self._speak(msg)

    def _autodo_allowed(self, bus) -> bool:
        """Silent auto-do is opt-in and tightly gated: trusted autonomy (level 3),
        the user actually present (a recent command), and not in quiet hours."""
        try:
            from core.trust_ladder import autonomy_level
            if autonomy_level() < 3:
                return False
            snap = bus.snapshot()
            return bool(snap.recent_commands) and not snap.is_quiet_hours
        except Exception:
            return False

    def _auto_do(self, thought) -> None:
        """Execute a trusted anticipated action on the user's behalf and report
        it. Routed through process_text so it takes the full pipeline under the
        re-entrant lock, and audit-logged so every self-initiated act is visible."""
        try:
            from core.log_setup import event as _event
            _event("auto_action", command=thought.command, kind=thought.kind)
        except Exception:
            pass
        try:
            resp = self.process_text(thought.command)
        except Exception as e:
            log.debug("[cognition] auto-do failed: %s", e)
            return
        self._speak_proactive(resp or thought.message, reason=f"autodo:{thought.kind}")

    def _run_consolidation(self) -> None:
        """The agent's nightly 'sleep' — summarize the day into durable memory,
        then line up the next night. Wired to the local LLM as summarizer."""
        try:
            from core.memory_consolidation import get_consolidator, schedule_nightly
            c = get_consolidator()
            c.set_llm(lambda p: (self.llm.reply(p, "neutral", {}, []) or ""))
            summary = c.consolidate()
            if summary:
                log.info("[consolidate] %s", summary)
            # Continuity C4: after the nightly sleep, push the fresh
            # personal-facts slice to the phone so its Tier-3 brain wakes
            # up knowing today's new facts. Best-effort — no phone, no cry.
            try:
                from core.continuity import get_router
                if get_router().push_memory_slice():
                    log.info("[consolidate] memory slice pushed to phone")
            except Exception as e:
                log.debug("[consolidate] mem slice push skipped: %s", e)
            # Overnight the routine-learner may have graduated new patterns —
            # materialize the safe ones into the live automation executor (and
            # retire any the user reverted). Governed: only reversible routines
            # auto-enable; risky ones stay confirm-gated. See graduated_routines.
            try:
                from core.automation import get_engine as _auto_engine
                from core.graduated_routines import sync as _sync_graduated
                res = _sync_graduated(_auto_engine())
                if res["created"] or res["retired"]:
                    log.info("[graduated] +%d live, -%d retired",
                             len(res["created"]), len(res["retired"]))
            except Exception as e:
                log.debug("[engine] graduated-routine sync skipped: %s", e)
            # S1: nightly audit-chain verification — tamper = loud warning.
            try:
                from core.autonomy import get_gate
                ok, bad = get_gate().ledger.verify()
                if not ok:
                    log.warning("[ledger] HASH CHAIN BROKEN at line %s — "
                                "audit trail may be tampered", bad)
            except Exception:
                pass
            if self.scheduler is not None:
                schedule_nightly(self.scheduler)
        except Exception as e:
            log.debug("[engine] consolidation run failed: %s", e)

    # ------------------------------------------------------------------ #
    #  Audio                                                               #
    # ------------------------------------------------------------------ #

    def _ensure_io(self) -> None:
        if self._stt is None:
            from core.stt import STT
            self._stt = STT()
        if self._tts is None:
            from core.tts import TTS
            self._tts = TTS()

    def _speak(self, text: str) -> None:
        if not text:
            return
        if self._tts is None:
            print(f"{_settings.assistant_name()}: {text}")
        else:
            self._tts.speak(text)

    # ------------------------------------------------------------------ #
    #  Pure pipeline (testable without audio I/O)                         #
    # ------------------------------------------------------------------ #

    def process_text(self, text: str, *, source: str = "laptop"
                     ) -> Optional[str]:
        """Run the full brain pipeline on a single utterance.

        Returns the assistant's response text, or None if the utterance was
        empty / silent. All side effects (state changes, DB writes, memory
        writes) happen inside.

        Thread-safe: serialized by an RLock — callable from the GUI brain
        worker AND the cloud-bridge thread without interleaving turns.

        ``source`` names the body the utterance came from ("laptop" |
        "phone") — it feeds the continuity DeviceRegistry so proactive
        replies later go to wherever the user actually is.

        Multi-command utterances ("X aur Y") are split into segments and
        each segment runs through the brain pipeline independently. The
        responses are joined with newlines.
        """
        if text and text.strip():
            try:
                from core.continuity import get_router
                get_router().registry.beat(source, "active")
            except Exception:
                pass
        _turn_started = time.time()
        with self._pt_lock:
            self._turn_from_alias = False
            resp = self._process_text_inner(text)
            # Self-correction (P3): record how this turn went while still
            # holding the turn lock, so a concurrent phone command can't
            # interleave and make an unrelated turn look like the repair of
            # this one. `last_dispatch` is the engine's own "did a skill
            # actually fire" signal, set at the dispatch seam.
            if self.repair is not None:
                self._note_repair_turn(text, _turn_started)
        # Feed the Context Bus (Phase 2) + learn habits for Anticipation (Phase 4).
        # Real sessions only (tts != "SKIP") so headless tests never pollute the
        # learned model or context. Best-effort — never breaks the pipeline.
        if self._tts != "SKIP":
            try:
                from core import anticipation, context_bus
                bus = context_bus.get()
                snap = bus.snapshot()                 # BEFORE recording current turn
                prev = snap.recent_intents[-1] if snap.recent_intents else None
                _intent = (getattr(self, "last_dispatch", None) or {}).get("skill")
                anticipation.get().observe(prev, text, _intent or "", snap.time_of_day)
                bus.record_command(text, _intent)
                # Phase 4 surface: append an anticipation offer when warranted.
                if resp is not None:
                    resp = self._maybe_offer(resp, snap.time_of_day, _intent, text)
            except Exception:
                pass
        # Surface the proactive emotional check-in only in a real session —
        # headless test engines run with tts="SKIP" and assert exact command
        # output, so the emotional layer must not append to their replies.
        if resp is not None and self._tts != "SKIP":
            before = resp
            resp = self._affect_care(resp)
            if resp == before:                    # no check-in → maybe colour tone
                resp = self._affect_tone(resp)
        return resp

    def _record_decline(self, goal) -> None:
        """Write a `declined` row for the action a parked goal was asking about.

        Deliberately a NEW decision value rather than reusing `deny`:
        `Ledger._today()` — and therefore every budget and rate cap — counts
        only `allow` rows, so this cannot inflate spend or rate limits, while
        `trust_promotion` can still see it. Best-effort; a bookkeeping failure
        must never cost the user their "cancel".
        """
        try:
            from core import autonomy
            from core.goal_system import declined_action
            action, args = declined_action(goal)
            if not action:
                return
            gate = autonomy.get_gate()
            gate.ledger.record(
                action=action, args=args, cls=autonomy.classify(action),
                level=autonomy.L3_ACT, decision="declined",
                why="user answered no to the confirmation",
                result="DECLINED")
        except Exception as e:
            log.debug("[engine] decline not recorded: %s", e)

    def _note_repair_turn(self, text: str, turn_started: float) -> None:
        """Feed one finished turn to the repair memory. Best-effort — a
        learning hiccup must never cost the user their reply."""
        try:
            d = getattr(self, "last_dispatch", None) or {}
            # `last_dispatch` is a side-channel the engine never clears — only
            # its callers do. So a chat/fallback turn can still be carrying the
            # PREVIOUS turn's dispatch, and trusting it here would record a
            # miss as a success and teach the alias backwards. The dispatch's
            # own timestamp settles it: only a dispatch stamped after this turn
            # began belongs to this turn.
            fresh = float(d.get("ts") or 0.0) >= turn_started
            # "executed" only: an asked_slot turn hasn't done the thing yet,
            # and treating it as success would teach off a question rather
            # than off an outcome.
            ok = fresh and d.get("action") == "executed" and bool(d.get("intent"))
            learned = self.repair.note_turn(
                text,
                intent=d.get("intent") if fresh else None,
                confidence=d.get("confidence", 0.0) if fresh else 0.0,
                ok=ok, from_alias=self._turn_from_alias)
            if learned:
                # The alias is far more useful with the repair turn's slots:
                # an exact repeat of the phrase then reproduces the exact
                # action, not just the intent.
                slots = getattr(self, "_turn_slots", None)
                if isinstance(slots, dict) and slots:
                    self.repair.remember_slots(learned, slots)
        except Exception as e:
            log.debug("[repair] note_turn failed: %s", e)

    def _affect_care(self, resp: str) -> str:
        """Append a proactive emotional check-in when warranted (Sentient-Partner
        Phase 1). The Affective Core rate-limits this (max 1/30 min), suppresses it
        during quiet hours, and honours the AERIS_AFFECT_OFF kill switch — so it can
        never nag. Best-effort: never breaks the reply."""
        try:
            from core import affect
            core = affect.get()
            care = core.care_moment()
            if care:
                resp = f"{resp}\n\n{care}" if resp else care
                core.persist()
        except Exception:
            pass
        return resp

    # Colour tone at most this often, so an off mood warms the voice without
    # turning every single reply into an empathy sandwich.
    _TONE_COOLDOWN_S = 300.0

    def _affect_tone(self, resp: str) -> str:
        """Occasionally colour a reply so its *tone* matches a clearly non-neutral
        mood — a brief empathetic opener (Sentient-Partner P1 deepening: the
        partner sounds like it feels, not just acts). Never changes the content,
        skips neutral moods, rate-limited (see _TONE_COOLDOWN_S), honours
        AERIS_AFFECT_OFF. Best-effort — never breaks the reply."""
        try:
            from core import affect
            core = affect.get()
            if core.mood() == "neutral":
                return resp
            import time as _t
            now = _t.time()
            if now - getattr(self, "_last_tone_at", 0.0) < self._TONE_COOLDOWN_S:
                return resp
            coloured = core.modulate(resp)
            if coloured != resp:                  # only "spend" the cooldown on a real change
                self._last_tone_at = now
                return coloured
        except Exception:
            pass
        return resp

    def _resolve_pending(self, text: str) -> Optional[str]:
        """If AERIS just made an anticipation OFFER ("gmail kholo karoon?"), a
        confirmation runs it; anything else drops the offer. Returns the command
        to run, or None. (Sentient-Partner Phase 4 surface.)"""
        pending = getattr(self, "_pending_suggestion", None)
        if pending is None:
            return None
        self._pending_suggestion = None          # single-shot either way
        try:
            from core.confirm_gate import is_confirmation
            if is_confirmation(text):
                return pending
        except Exception:
            pass
        return None

    def _recently_offered(self, cmd: Optional[str], *, now: Optional[float] = None,
                          window: float = 1200.0) -> bool:
        """True if this exact command was proactively offered within `window`
        (shared by the Anticipation offer and the Cognition habit thought so
        they never double-surface the same suggestion). Records it either way."""
        if not cmd:
            return False
        import time as _t
        now = _t.time() if now is None else now
        if cmd == getattr(self, "_last_offered_cmd", None) and \
                (now - getattr(self, "_last_offered_at", 0.0)) < window:
            return True
        self._last_offered_cmd = cmd
        self._last_offered_at = now
        return False

    def _maybe_offer(self, resp: Optional[str], time_of_day: str,
                     cur_intent: Optional[str], just_said: str) -> Optional[str]:
        """Append an anticipation offer to the reply when warranted — trust-gated
        (Anticipator.suggest already vets it), rate-limited (>=3 min apart), never
        during slot-fill, and never re-offering what was just done."""
        import time as _t
        try:
            if self.state.is_waiting_slot():
                return resp
        except Exception:
            return resp
        now = _t.time()
        if now - getattr(self, "_last_suggest_at", 0.0) < 180.0:
            return resp
        try:
            from core import anticipation
            s = anticipation.get().suggest(time_of_day, cur_intent)
        except Exception:
            return resp
        if not s or s.command.strip().lower() == (just_said or "").strip().lower():
            return resp
        if self._recently_offered(s.command):     # Cognition already raised it
            return resp
        self._pending_suggestion = s.command
        self._last_suggest_at = now
        offer = f"Waise — {s.command} karoon?"
        return f"{resp}\n\n{offer}" if resp else offer

    def _process_text_inner(self, text: str) -> Optional[str]:
        if not text or not text.strip():
            return None

        text = text.strip()

        # Anticipation offer resolution (Phase 4 surface): a "haan" after an offer
        # replays the suggested command; otherwise the offer is silently dropped.
        _confirmed = self._resolve_pending(text)
        if _confirmed is not None:
            return self._process_segment(_confirmed) or "Ho gaya."

        # ── Step 0a: slot-filling in progress ──
        if self.state.is_waiting_slot():
            if _is_cancel(text):
                self.state.reset()
                return "Theek hai, cancel kar diya."
            # New-command rescue: if the "answer" is VERBATIM a known command
            # (exact pattern match), the user abandoned the half-finished command
            # and issued a new one ("note banao" → then "coin toss karo") — run it
            # instead of storing it as the slot value. Exact-match ONLY, so
            # free-form slot content ("buy milk") is never hijacked.
            try:
                _em = self.brain.classifier.exact_match(text)
                if _em and _em != (self.state.current_state or {}).get("intent"):
                    self.state.reset()
                    return (self._process_segment(text)
                            or "Theek hai, cancel kar diya.")
            except Exception as _e:
                log.debug("[engine] slot-fill new-command rescue skipped: %s", _e)
            # Re-run entity extraction on the answer so "with raj" → "raj",
            # "5 baje" → "5 baje", etc. — instead of storing the raw answer.
            intent = self.state.current_state["intent"]
            waiting_for = self.state.current_state["waiting_for"]
            extracted = self.entity_extractor.extract(text, intent)
            answer_text = extracted.get(waiting_for, text).strip()
            return self._render_state_result(self.state.handle_follow_up(answer_text))

        # ── Step 0b: disambiguation in progress ──
        if self.state.is_waiting_disambig():
            if _is_cancel(text):
                self.state.reset()
                return "Theek hai, cancel kar diya."
            return self._handle_disambig_answer(text)

        # ── Step 0c: destructive action awaiting confirmation ──
        # One-turn window: "haan"/"pakka" runs the parked skill, anything
        # else (including cancel) aborts it. See core/confirm_gate.py.
        if self._pending_confirm is not None:
            from core.confirm_gate import is_confirmation
            intent, slots = self._pending_confirm
            self._pending_confirm = None
            if is_confirmation(text):
                out = self.executor.execute(intent, slots)
                try:
                    self.dialogue.note(intent, slots,
                                       slots.get("raw_text", ""), out or "")
                except Exception:
                    pass
                return out
            if _is_cancel(text):
                return "Theek hai, cancel kar diya — kuch delete nahi hua."
            # Any OTHER input: abort the parked action AND process the new
            # input normally (pending already cleared → recursion is safe).
            rest = self.process_text(text)
            note = "Pehla wala action cancel kar diya. "
            return note + rest if rest else note.strip()

        # ── Step 0d: proactive OFFER awaiting "haan" (one turn) ──
        # "haan" activates the offered mode; anything else silently drops the
        # offer and the input is processed normally (no scary cancel message).
        if self._pending_offer is not None:
            from core.confirm_gate import is_confirmation
            intent, slots = self._pending_offer
            self._pending_offer = None
            if is_confirmation(text):
                out = self.executor.execute(intent, slots)
                try:
                    self.dialogue.note(intent, slots,
                                       slots.get("raw_text", ""), out or "")
                except Exception:
                    pass
                return out
            # else: fall through — offer dropped, process this input normally.

        # ── Step 1: pending feedback (within one-turn window) ──
        if self._pending_utterance_id is not None:
            if _is_correction(text):
                self.feedback.record_feedback(self._pending_utterance_id, "corrected")
                self._pending_utterance_id = None
                return "Sorry. Phir se batao kya karna hai?"
            # Any other input means the prior execution was implicitly accepted.
            self.feedback.record_feedback(self._pending_utterance_id, "accepted")
            self._pending_utterance_id = None

        # ── Step 1.5: "what did you just say?" — answer from dialogue context ──
        again = say_again_reply(text, self.dialogue)
        if again:
            return again

        # ── Step 2a: memory-RECALL first (more specific — needs interrogative form) ──
        # Recall runs on the FULL utterance before splitting so that
        # "mera naam kya hai aur mera ghar kahan hai" is still treated as
        # a single recall pattern (the splitter would otherwise fragment it).
        recall = self.memory.detect_and_recall(text)
        if recall:
            self.history.add_user(text, "neutral")
            self.history.add_assistant(recall)
            return recall

        # ── Step 2b: memory-SET commands ──
        ack = self.memory.detect_and_store(text)
        if ack:
            self.history.add_user(text, "neutral")
            self.history.add_assistant(ack)
            return ack

        # ── Step 2c: memory-FORGET commands (reversible via undo) ──
        forget_ack = self.memory.detect_and_forget(text)
        if forget_ack:
            self.history.add_user(text, "neutral")
            self.history.add_assistant(forget_ack)
            return forget_ack

        # ── Step 2e: PANIC / resume (Q1·M3) — instant global halt ──
        _low = text.strip().lower()
        if re.search(r"\b(bilkul ruk ja|sab band kar do|sab rok do|"
                     r"emergency stop|stop everything|panic)\b", _low):
            try:
                from core import autonomy
                autonomy.set_panic(True)
            except Exception:
                pass
            msg = "Sab kuch rok diya — autonomy off (L0). 'resume karo' bolo."
            self.history.add_user(text, "neutral")
            self.history.add_assistant(msg)
            return msg
        if re.search(r"\b(resume karo|panic off|wapas normal|autonomy on)\b",
                     _low):
            try:
                from core import autonomy
                autonomy.set_panic(False)
            except Exception:
                pass
            msg = "Theek hai, wapas normal. Autonomy on."
            self.history.add_user(text, "neutral")
            self.history.add_assistant(msg)
            return msg

        # ── Step 2f: SELF-QUERY (Blueprint M1) — the agent knows itself ──
        if re.search(
                r"\b(tu|tum|aeris|tumhare)\b.*\b(kaisa hai|kaise ho|kya kar "
                r"sakt|kya kar sakte|abhi kya kar|kaun ho|capabilit)\b", _low) \
                or re.search(r"\b(ye|yeh|iska|tu ne).*(kyun kiya)\b", _low) \
                or _low in ("tu kaisa hai", "aeris kaisa hai"):
            try:
                from core.self_model import get_self_model
                reply = get_self_model().describe(_low)
                self.history.add_user(text, "neutral")
                self.history.add_assistant(reply)
                return reply
            except Exception as e:
                log.debug("[engine] self-query skipped: %s", e)

        # ── Step 2d: capture a STANDING GOAL (Q1·M2) ──
        # "yaad dilana… / help me plan… / keep an eye on…" is a persistent
        # intention, not a one-shot command — hold it and ack.
        try:
            from core import goal_system
            g = goal_system.get_goal_store().capture(text, source="voice")
            if g is not None:
                ack = goal_system.capture_ack(g)
                self.history.add_user(text, "neutral")
                self.history.add_assistant(ack)
                return ack
        except Exception as e:
            log.debug("[engine] goal capture skipped: %s", e)

        # ── Step 2g: learn a stated PREFERENCE (Blueprint loop 1) ──
        # "I prefer… / mujhe … pasand / next time …" → durable memory the
        # planner recalls later. Conservative — never catches commands.
        try:
            from core import preference_learner
            pref = preference_learner.get_learner().learn(text)
            if pref is not None:
                msg = preference_learner.ack(pref)
                self.history.add_user(text, "neutral")
                self.history.add_assistant(msg)
                return msg
        except Exception as e:
            log.debug("[engine] preference learn skipped: %s", e)

        # ── Step 2h: answer a PARKED goal's confirmation (Q1·M3 cycle) ──
        # If a goal recently asked "…haan ya cancel?", a "haan" resumes it with
        # the action pre-approved; a "cancel" drops it.
        try:
            from core import goal_system
            from core.confirm_gate import is_confirmation
            pending = goal_system.get_goal_store().awaiting_confirmation(
                within_s=300)
            if pending is not None:
                if is_confirmation(text) and self.agent is not None:
                    res = goal_system.advance(
                        goal_system.get_goal_store(), pending, self.agent,
                        approve_last=True)
                    reply = res.reply
                    self.history.add_user(text, "neutral")
                    self.history.add_assistant(reply)
                    return reply
                if re.search(r"^(cancel|nahi|na|mat karo|rehne do|band karo|"
                             r"chhod do)$", _low):
                    goal_system.get_goal_store().drop(pending)
                    # Record the refusal (§6.33). Until this existed, saying
                    # "cancel" left NO trace anywhere: the ledger held the
                    # `confirm`/PARKED row but nothing about how it resolved,
                    # so a class the user kept refusing looked identical to
                    # one they never had to be asked about — and
                    # `trust_promotion` would cheerfully propose raising it.
                    self._record_decline(pending)
                    msg = "Theek hai, cancel kar diya."
                    self.history.add_user(text, "neutral")
                    self.history.add_assistant(msg)
                    return msg
        except Exception as e:
            log.debug("[engine] confirm-answer skipped: %s", e)

        # ── Step 2i: manage a LEARNED routine by voice (Blueprint loop 3) ──
        # "auto kar do" accepts the offer just surfaced; "rehne do" rejects it;
        # "morning routine band karo" reverts a running auto-routine. Handled by
        # the trust-aware offers layer; a graduate/revert is materialized into
        # the live executor right away (not just at the nightly sync).
        try:
            from core import routine_voice, routine_offers
            from core.routine_graduation import get_tracker
            _tr = get_tracker()
            reply = routine_voice.handle(
                text,
                pending_fn=lambda: routine_offers.pending_offers(tracker=_tr),
                active_fn=lambda: routine_offers.active_routines(tracker=_tr),
                accept_fn=lambda k: routine_offers.accept(k, tracker=_tr),
                reject_fn=lambda k: routine_offers.reject(k, tracker=_tr),
                revert_fn=lambda k: routine_offers.revert(k, tracker=_tr),
            )
            if reply is not None:
                if routine_voice.classify(text) in ("accept", "revert"):
                    try:
                        from core.automation import get_engine as _ae
                        from core.graduated_routines import sync as _sync
                        _sync(_ae())
                    except Exception:
                        pass
                self.history.add_user(text, "neutral")
                self.history.add_assistant(reply)
                return reply
        except Exception as e:
            log.debug("[engine] routine-voice skipped: %s", e)

        # ── Step 2j: TEMPORAL recall (Blueprint I2) — "kal kya kiya tha?" ──
        # Window-word + ask-verb dono chahiye, isliye "kal alarm laga do"
        # jaise commands isse kabhi nahi pakde jaate.
        try:
            from core import temporal_recall
            from core.presence_journal import get_journal
            from core.goal_system import get_goal_store
            from core.autonomy import get_gate
            t_ans = temporal_recall.answer(
                text, time.time(), journal=get_journal(),
                goal_store=get_goal_store(), ledger=get_gate().ledger)
            if t_ans is not None:
                self.history.add_user(text, "neutral")
                self.history.add_assistant(t_ans)
                return t_ans
        except Exception as e:
            log.debug("[engine] temporal recall skipped: %s", e)

        # ── Step 3: cancel keyword with no live state ──
        if _is_cancel(text):
            return "Kuch chal nahi raha cancel karne ke liye, sir."

        # ── Step 4: split into segments and run pipeline per segment ──
        # Chatty utterances are NEVER split: "yaar thak gaya hoon, kya
        # karoon" is one thought, not two commands — splitting it hands
        # fragments to the k-NN where they misroute.
        #
        # Exact-match short-circuit: if the WHOLE utterance is a verbatim
        # skill pattern ("phone pair karo", "lock screen"), it's certainly
        # a command — skip the chat gate entirely. This (a) avoids a
        # pointless second encoder forward per command and (b) dodges the
        # torch .to() heap-corruption seen on that encode path. exact_match
        # is a dict lookup — no encoding, no crash surface.
        try:
            _exact = self.brain.classifier.exact_match(text)
        except Exception:
            _exact = None
        if _exact:
            segments = split_into_segments(text)
        else:
            from core.chat_gate import is_chatty_hybrid
            if is_chatty_hybrid(text):
                segments = [text]
            else:
                segments = split_into_segments(text)
        responses: list[str] = []
        for seg in segments:
            seg_response = self._process_segment(seg)
            if seg_response:
                responses.append(seg_response)

        if not responses:
            return None
        return "\n".join(responses)

    # Intents a reminder-signal utterance is allowed to land on (reminder-adjacent).
    _REMINDER_FAMILY = {"set_reminder", "set_timer", "add_task",
                        "append_note", "create_note", "schedule_meeting"}

    def _force_intent(self, pred, intent: str):
        return type(pred)(
            intent=intent,
            confidence=max(getattr(pred, "confidence", 0.0), 0.92),
            top3=[(intent, 1.0)],
            raw_text=pred.raw_text,
            normalized_text=pred.normalized_text,
        )

    def _guard_dangerous_route(self, text: str, pred):
        """Block the measured dangerous mis-routes: a clear reminder request must
        never reach a destructive/unrelated skill, and 'X kholo/open' must never
        log an expense or roll dice. Only fires on a clear signal + a wrong intent,
        so normal routing is untouched."""
        import re
        low = (text or "").lower()
        intent = getattr(pred, "intent", None)
        if not intent:
            return pred
        # (1) Reminder request → must stay in the reminder family (was hitting
        # empty_recycle_bin, dice_roll, sleep_cycle…). "yaad dila/rakh", not the
        # memory-recall "yaad hai".
        if intent not in self._REMINDER_FAMILY and \
                re.search(r"\byaad\s+(dila|rakh)|\bremind\b|\breminder\b", low):
            return self._force_intent(pred, "set_reminder")
        # (2) "open X" → never add_expense / dice_roll etc.
        if intent in {"add_expense", "dice_roll", "empty_recycle_bin"} and \
                re.search(r"\b(khol|kholo|kholna|khol\s*do|open|launch)\b", low):
            is_site = bool(re.search(r"\.(com|in|org|net|io|co|ai)\b|website|\bsite\b", low))
            return self._force_intent(pred, "open_website" if is_site else "open_app")
        # (3) Weather query landed on a NON-weather skill — most dangerously
        # set_reminder (which would CREATE a reminder!), also day_of_week /
        # fun_fact / age_calc / detect_holding. Rescue to the local-weather skill.
        # Fires only when the intent is OUTSIDE the weather family, so a correct
        # weather_for_city / real_weather (city or forecast) route is left alone.
        if intent not in {"weather_local", "weather_for_city", "real_weather",
                          "get_weather"} and \
                re.search(r"\b(mausam|weather|baarish|barish|garmi|thand)\b", low):
            return self._force_intent(pred, "weather_local")
        # (4) System-status query landed on an unrelated skill ("system info" →
        # whoami_info, "performance batao" → brain_health, "cpu aur ram" →
        # work_power, "system ka haal" → fun_fact). Rescue to system_stats; the
        # cpu/ram/disk anchors already catch the common phrasings, this the rest.
        if intent not in {"system_stats", "system_info", "memory_stats",
                          "disk_space", "cpu_info", "system_uptime"} and \
                re.search(r"\bsystem\s+(info|information|stats|ka\s+haal)\b|"
                          r"\bcpu\s+aur\s+ram\b|"
                          r"\bperformance\s+(batao|dikhao|kaisi|kaisa|check)\b", low):
            return self._force_intent(pred, "system_stats")
        # (5) Screenshot request landed on repeat_last ('ss lelo'). Rescue to
        # screenshot_full; the other screenshot phrasings already route there.
        if intent not in {"screenshot_full", "screenshot_window",
                          "screenshot_to_phone", "screenshots_folder",
                          "take_screenshot"} and \
                re.search(r"\bscreenshot\b|\bscreen\s+(shot|capture)\b|"
                          r"\bscreen\s+ka\s+photo\b|\bss\s+le", low):
            return self._force_intent(pred, "screenshot_full")
        # (6) Note-creation request landed on an unrelated skill — most harmfully
        # add_expense (logs a JUNK expense!), also password_generate / calculate /
        # todays_meetings. Rescue to create_note. Fires only outside the note
        # family so a correct append_note / scratchpad edit is left alone. "note"
        # is \b-bounded so footnote/banknote don't trip it.
        if intent not in {"create_note", "append_note", "scratchpad_summarize",
                          "scratchpad_append"} and \
                re.search(r"\bnote\s+(banao|bana\s+do|create|likho|save|karo|"
                          r"kar\s+lo|me\s+(likho|add))\b|"
                          r"\b(likho|likh\s+do|add)\s+(a\s+|ye\s+|ek\s+)?note\b", low):
            return self._force_intent(pred, "create_note")
        # (7) Chat/memory WIPE skills are destructive — they must fire only on an
        # EXPLICIT wipe request. "ek pep talk do" was routing to clear_chat, which
        # would ERASE the conversation. Predicted without a clear/reset/wipe word
        # → treat as k-NN drift and drop to the LLM chat instead.
        if intent in {"clear_chat", "clear_memory", "clear_history",
                      "forget_all"} and \
                not re.search(r"\b(clear|reset|wipe|erase|delete|hata|mita|saaf|"
                              r"naya\s+(chat|conversation)|fresh\s+start|start\s+over|"
                              r"purani\s+baat|chat\s+history|forget)\b", low):
            return self._force_intent(pred, "ask_jarvis")
        # (8) "give me ideas / brainstorm X" landed on an unrelated skill (was
        # scattering to add_expense — a junk expense — plus next_birthday,
        # play_youtube, bill_split, current_date). Rescue to brainstorm_ideas.
        if intent != "brainstorm_ideas" and \
                re.search(r"\bbrainstorm\b|\bsuggest\s+(some\s+)?ideas?\b|"
                          r"\bideas?\s+(do|de\s+do|dedo|chahiye|batao|for)\b", low):
            return self._force_intent(pred, "brainstorm_ideas")
        return pred

    def _process_segment(self, text: str) -> Optional[str]:
        """Run brain prediction + execution on a single command segment.

        This is the per-segment version of the original pipeline tail
        (sentiment + brain + threshold + disambig + execute / fallback).
        Memory / state / cancel checks have already happened in
        process_text() against the full utterance.
        """
        if not text or not text.strip():
            return None

        # Pronoun → referent rewrite BEFORE classification. "ab isko band
        # karo" after "open notepad" becomes "ab notepad band karo", so the
        # brain routes to close_app(notepad) instead of confidently picking
        # a pronoun-blind intent (the tab_close/Ctrl+W misfire). Guarded —
        # returns None unless context is fresh, unambiguous, and the text
        # is a command with exactly one object pronoun.
        try:
            _rw = rewrite_pronoun(text, self.dialogue)
        except Exception:
            _rw = None
        # Elliptical analogy: "aur delhi ka?" after "weather in mumbai"
        # becomes "weather in delhi" — a full sentence every downstream
        # component (brain, extractor, raw-text-parsing skills) already
        # understands. Mutually exclusive with the pronoun rewrite.
        if _rw is None:
            try:
                _rw = analogy_rewrite(text, self.dialogue)
            except Exception:
                _rw = None
        if _rw:
            text = _rw

        # Sentiment is per-segment so a "weather batao aur tu bekaar hai"
        # response can pick up the negative tone of the second clause.
        sentiment = self.sentiment.classify(text)

        # Affective Core: fold this turn's tone into AERIS's running mood model
        # (Sentient-Partner Phase 1). Best-effort — the emotional layer must never
        # break the command pipeline; disabled via AERIS_AFFECT_OFF=1.
        try:
            from core import affect
            affect.get().observe(sentiment.score)
        except Exception:
            pass

        # Exact-match fast path: if the whole segment is a verbatim skill
        # pattern, build the prediction from a dict lookup and skip the
        # subspan scanner entirely. The scanner calls brain.predict on many
        # trimmed variants — each a torch encoder forward whose .to() can
        # heap-corrupt this process (conflicting native runtimes + torch).
        # Exact commands ("phone pair karo", "lock screen") thus do ZERO
        # encoding — instant and crash-free.
        # Tier 0: a phrasing the USER taught us by rephrasing after a miss
        # (core/repair_memory.py). It sits above exact_match on purpose —
        # the user is more authoritative about their own phrasing than the
        # corpus is, and in practice the two never collide: a phrase that
        # exact_match already resolves never missed, so no alias was ever
        # learned for it. Cheapest tier there is: one dict lookup, no encode.
        _exact_intent = None
        self._turn_from_alias = False
        if self.repair is not None:
            try:
                _alias = self.repair.lookup(text)
            except Exception:
                _alias = None
            if _alias is not None:
                _exact_intent = _alias.intent
                self._turn_from_alias = True
                log.debug("[repair] %r → %s (learned)", text, _alias.intent)
        try:
            if not _exact_intent:
                _exact_intent = self.brain.classifier.exact_match(text)
        except Exception:
            _exact_intent = None
        if _exact_intent:
            from core.intent_classifier import Prediction as _Pred
            _norm_t = self.brain.classifier.normalizer.clean(text)
            pred = _Pred(intent=_exact_intent, confidence=1.0,
                         top3=[(_exact_intent, 1.0)], raw_text=text,
                         normalized_text=_norm_t)
            winning_span = text
        else:
            # Subspan scanner: tries the full segment plus a few trimmed
            # variants and picks the highest-confidence interpretation.
            # This lets "ek kam karo notepad open karo" be recognised as
            # open_app instead of volume_down ("kam karo" is filler here).
            # winning_span is used ONLY for intent classification — entity
            # extraction still runs on the full segment.
            pred, winning_span = find_best_interpretation(text, self.brain)

        # Gazetteer override: if the segment contains a known app name AND
        # an open/close verb, trust that structural evidence over the brain's
        # cosine vote. Two reasons to fire:
        #   (a) the brain disagrees ("brave open karo" → volume_up) — replace
        #       the wrong prediction with the structural one;
        #   (b) the brain agrees but its top3 is split between open/close,
        #       which would otherwise trigger a needless disambig prompt
        #       ("ek kam karo notepad open karo" had open_app=0.42, close_app=0.37).
        # In both cases we collapse top3 to a single high-confidence pick.
        hint = self.entity_extractor.intent_hint(text)
        if hint:
            pred = type(pred)(
                intent=hint,
                confidence=max(pred.confidence, 0.90),
                top3=[(hint, 1.0)],
                raw_text=pred.raw_text,
                normalized_text=pred.normalized_text,
            )

        # ── Safety guard: block measured dangerous mis-routes ─────────────
        # A reminder request ("yaad dilana bill bharne ka") was routing to
        # empty_recycle_bin (data loss!); an "X kholo" was routing to
        # add_expense (logs a fake expense). Structural signal beats the cosine
        # vote here. See docs/ROUTING_ACCURACY_AUDIT.md.
        pred = self._guard_dangerous_route(text, pred)

        intent_for_threshold = pred.intent or "_unknown"
        threshold = self.feedback.get_threshold(intent_for_threshold)

        # ── Context rescue: elliptical follow-up of the previous turn ──
        # "weather in mumbai" → "aur delhi ka?": the brain alone scores the
        # fragment below threshold, but the dialogue context recognises it
        # as the previous intent with one entity swapped. Only fires when
        # the brain is NOT confident — a confident classification always
        # wins over context guessing.
        ctx_entities: Optional[dict] = None
        if not (pred.intent and pred.confidence >= threshold) \
                and self.dialogue.fresh():
            try:
                fu_extract = self.entity_extractor.extract(
                    text, self.dialogue.last_intent)
            except Exception:
                fu_extract = {}
            fu = self.context.followup_intent(text, False, fu_extract)
            if fu:
                fu_intent, ctx_entities = fu
                pred = type(pred)(
                    intent=fu_intent,
                    confidence=0.96,
                    top3=[(fu_intent, 0.96)],
                    raw_text=pred.raw_text,
                    normalized_text=pred.normalized_text,
                )
                threshold = self.feedback.get_threshold(fu_intent)

        self.history.add_user(text, sentiment.label)

        # ── Chit-chat gate ──
        # Conversational utterances ("yaar thak gaya...", "tumhara kya
        # khayal hai") were being confidently *stolen* by loosely-matching
        # skills (k-NN cosine noise: play_music at 0.82, help_catalog at
        # 0.85). v2: encoder-based classifier (chat_gate) with the keyword
        # heuristic as floor/fallback.
        #
        # Bypass bar depends on HOW the confidence was earned:
        #   * full-text match (winning_span == text) → ≥0.90 may dispatch
        #     ("mausam kaisa hai aaj mumbai mein" @0.91 is a real command)
        #   * trimmed-subspan match → ≥0.99 (exact only). The subspan
        #     scanner chops words until SOMETHING scores high — that
        #     inflated 0.93 stole "kal raat neend nahi aayi kya karu"
        #     for conversation_recap. Cherry-picked confidence doesn't
        #     outrank the chat gate.
        _full_span = (winning_span or "").strip().lower() == text.strip().lower()
        _gate_bar = CHAT_GATE_CONFIDENCE if _full_span else 0.99
        # Confidence FIRST (short-circuits before is_chatty_hybrid): a
        # confident command never pays the chat-gate encoder forward — both
        # a speed win and it avoids the torch .to() heap-corruption path
        # for exact/high-confidence commands like "phone pair karo".
        if pred.confidence < _gate_bar:
            from core.chat_gate import is_chatty_hybrid
            _chatty = is_chatty_hybrid(text)
            if os.environ.get("AERIS_GATE_DEBUG"):
                print(f"[gate-debug] text={text!r} chatty={_chatty} "
                      f"conf={pred.confidence:.2f} intent={pred.intent} "
                      f"span={winning_span!r} full_span={_full_span} bar={_gate_bar}")
            if _chatty:
                return self._fallback(text, pred, sentiment)

        if pred.intent and pred.confidence >= threshold:
            # close call?
            if self.disambiguator.is_close_call(pred):
                utterance_id = self.feedback.log_utterance(
                    raw_text=text,
                    normalized_text=pred.normalized_text,
                    predicted_intent=pred.intent,
                    confidence=pred.confidence,
                    top3=pred.top3,
                    sentiment_label=sentiment.label,
                    sentiment_score=sentiment.score,
                    action_taken="asked_disambig",
                )
                self.state.set_awaiting_disambig(pred, text)
                self._disambig_utterance_id = utterance_id
                prompt = self.disambiguator.prompt(pred)
                self.history.add_assistant(prompt)
                return prompt

            # Entity extraction runs on the FULL segment text — never on
            # the trimmed winning span, since trimming can drop the very
            # token the slot needs ("chrome" in "chrome open karo" gets
            # cut if the brain's most-confident subspan is just "open karo").
            # A context follow-up rescue already carries merged entities.
            if ctx_entities is not None:
                entities = ctx_entities
            else:
                entities = self.entity_extractor.extract(text, pred.intent)
            # Pronoun → entity injection: "ab isko band karo" fills
            # app_name from the previous turn instead of asking again.
            try:
                entities = self.context.inject(
                    entities, pred.intent,
                    self._required_entities(pred.intent), text)
            except Exception:
                pass
            # Make the raw spoken text and predicted intent available to
            # plugin skills via the slots dict. Used by skills that need
            # the full phrase (e.g. web_jumps strips a trigger word off
            # the front to recover the remaining query).
            entities.setdefault("raw_text", text)
            entities.setdefault("raw_intent", pred.intent or "")
            _t0 = time.perf_counter()
            result_str = self.state.process_prediction(
                [{"intent": pred.intent, "probability": f"{pred.confidence:.3f}"}],
                entities,
            )
            _latency_ms = (time.perf_counter() - _t0) * 1000.0
            action = "executed" if result_str.startswith("SUCCESS_EXECUTE|") else "asked_slot"
            # Structured dispatch telemetry — one JSON line per executed/slot
            # intent. Feeds the activity digest skill, the "which skill fired"
            # chip, and any future /metrics consumer. Best-effort: a logging
            # hiccup must never break the response path.
            _dispatch_meta = {
                "ts": time.time(),
                "event": "skill_dispatch",
                "intent": pred.intent,
                "confidence": round(float(pred.confidence), 3),
                "action": action,
                "latency_ms": round(_latency_ms, 1),
                "sentiment": sentiment.label,
            }
            # Synchronous side-channel for the per-reply UI chip — set before
            # the event fan-out so a GUI reading engine.last_dispatch right
            # after process_text() always sees this turn's dispatch.
            self.last_dispatch = _dispatch_meta
            # Slots for the repair memory, on a plain attribute rather than in
            # _dispatch_meta on purpose: that dict is written to the event log,
            # and slots can carry message bodies and other private content.
            self._turn_slots = {k: v for k, v in (entities or {}).items()
                                if k not in ("raw_text", "raw_intent")}
            try:
                from core.log_setup import event as _event
                _event("skill_dispatch", **{
                    k: v for k, v in _dispatch_meta.items()
                    if k not in ("ts", "event")
                })
            except Exception:
                pass
            utterance_id = self.feedback.log_utterance(
                raw_text=text,
                normalized_text=pred.normalized_text,
                predicted_intent=pred.intent,
                confidence=pred.confidence,
                top3=pred.top3,
                sentiment_label=sentiment.label,
                sentiment_score=sentiment.score,
                action_taken=action,
            )
            if action == "executed":
                self._pending_utterance_id = utterance_id
            response = self._render_state_result(result_str)
            self.history.add_assistant(response or "")
            return response

        # low confidence → LLM chit-chat or rejection
        return self._fallback(text, pred, sentiment)

    # ------------------------------------------------------------------ #
    #  Sub-handlers                                                        #
    # ------------------------------------------------------------------ #

    def _handle_disambig_answer(self, text: str) -> str:
        pred, original_text = self.state.consume_disambig()
        utterance_id = getattr(self, "_disambig_utterance_id", None)
        chosen = self.disambiguator.parse_answer(text, pred)

        if not chosen:
            # The reply didn't pick an option. It may be a brand-NEW command
            # ("morse ya base convert?" → user just says "coin toss karo")
            # rather than a failed answer. If it routes CONFIDENTLY to an intent
            # that isn't one of the two we were disambiguating, abandon the
            # disambig and run it as a fresh command instead of swallowing it.
            if utterance_id is not None:
                self.feedback.record_feedback(utterance_id, "cancelled")
            try:
                fresh = self.brain.predict(text)
                opts = {o[0] for o in pred.top3[:2]}
                if (fresh.intent and fresh.intent not in opts
                        and fresh.confidence >= self.feedback.get_threshold(fresh.intent)):
                    return (self._process_segment(text)
                            or "Samajh nahi aaya. Cancel kar diya — phir se bolo.")
            except Exception as e:
                log.debug("[engine] disambig new-command rescue skipped: %s", e)
            return "Samajh nahi aaya. Cancel kar diya — phir se bolo."

        # Reward the prediction: accepted if user picked top-1, corrected otherwise.
        if utterance_id is not None:
            if chosen == pred.top3[0][0]:
                self.feedback.record_feedback(utterance_id, "accepted")
            else:
                self.feedback.record_feedback(utterance_id, "corrected", correct_intent=chosen)
            self._disambig_utterance_id = None

        # Now run the chosen intent against the original text.
        entities = self.entity_extractor.extract(original_text, chosen)
        result_str = self.state.process_prediction(
            [{"intent": chosen, "probability": "1.0"}], entities
        )
        response = self._render_state_result(result_str)
        self.history.add_assistant(response or "")
        return response

    def _fallback(self, text: str, pred, sentiment) -> str:
        # Quiet fact learning: durable personal facts revealed mid-chat
        # ("mujhe blue color pasand hai") land in the knowledge graph so
        # "mujhe kya pasand hai" answers later. High-precision regex
        # frames only — silent, ~0 ms (see core/fact_bridge.py).
        try:
            from core.fact_bridge import learn_from
            learn_from(text)
        except Exception:
            pass
        llm_up = self.llm.is_available()
        action = "chat_fallback" if llm_up else "rejected"
        utterance_id = self.feedback.log_utterance(
            raw_text=text,
            normalized_text=pred.normalized_text,
            predicted_intent=pred.intent,
            confidence=pred.confidence,
            top3=pred.top3,
            sentiment_label=sentiment.label,
            sentiment_score=sentiment.score,
            action_taken=action,
        )

        # Multi-step requests go through the agentic observe/act loop, which
        # can chain skills and react to each result. Simple one-shot requests
        # stay on the faster single-round-trip path below. The Interpreter (P5)
        # decides the understanding strategy; it also routes single-step
        # *reasoning queries* ("konsi file sabse purani hai") to the agent,
        # not just multi-step chains. Falls back to the old heuristic if off.
        _plan_strategy = None
        try:
            from core import interpreter
            _plan = interpreter.get().plan(
                text, has_tools=bool(self._enable_tool_calls),
                agent_available=(self.agent is not None))
            _want_agent = _plan.strategy == "agent"
            _plan_strategy = _plan.strategy
        except Exception:
            _want_agent = self._looks_multistep(text)
        if llm_up and self.agent is not None and _want_agent:
            try:
                result = self.agent.run(text)
            except Exception as e:
                log.warning("[agent] run failed, falling back: %s", e)
                result = None
            # A parked run (gate wants the user's OK) must outlive this turn:
            # persist it as a blocked goal so Step 2h's "haan"/"cancel"
            # handler can resume it with the action pre-approved.
            if result is not None and result.stopped_reason == "blocked":
                self._park_agent_run(text, result)
            if result and result.tool_calls > 0 and result.reply:
                self.history.add_assistant(result.reply)
                self._pending_utterance_id = utterance_id
                return result.reply

        # A purely conversational turn (the Interpreter's "chat" strategy — no
        # actionable verb) skips the tool round-trip entirely and goes straight
        # to chit-chat: faster, and no risk of a spurious tool call on small talk.
        # Unknown/errored plan (None) keeps the old behaviour and still tries tools.
        if llm_up and self._enable_tool_calls and _plan_strategy != "chat":
            from core.tool_select import select_tools
            tools = select_tools(
                text, tools_manifest() + self._builtin_tools_manifest(),
                top_intents=pred.top3)
            raw = self.llm.reply_with_tools(
                user_text=text,
                sentiment_label=sentiment.label,
                memory_facts=self.memory.all_facts(),
                history=self.history.as_messages(),
                tools=tools,
            )
            if raw:
                call = parse_tool_response(raw)
                routed = self.tool_router.execute(call)
                if routed:
                    self.history.add_assistant(routed)
                    if call.kind == "tool":
                        self._pending_utterance_id = utterance_id
                    return routed

        if llm_up:
            # Reasoning cache (issue #7): only on the purely conversational path,
            # and only for stable, non-stateful questions — so the weak model
            # answers repeats instantly and consistently, never staler than the
            # TTL. Anything about live state is refused by is_cacheable().
            _chat = _plan_strategy == "chat"
            if _chat:
                try:
                    from core import reasoning_cache
                    hit = reasoning_cache.get().get(text)
                    if hit:
                        self.history.add_assistant(hit)
                        return hit
                except Exception:
                    pass
            reply = self.llm.reply(
                user_text=text,
                sentiment_label=sentiment.label,
                memory_facts=self.memory.all_facts(),
                history=self.history.as_messages(),
            )
            if reply:
                self.history.add_assistant(reply)
                if _chat:
                    try:
                        from core import reasoning_cache
                        reasoning_cache.get().put(text, reply)
                    except Exception:
                        pass
                return reply

        self.feedback.queue_low_confidence(utterance_id, text, pred.top3)
        msg = "Ye samajh nahi paaya, sir. Aap thoda clear bolenge?"
        self.history.add_assistant(msg)
        return msg

    def _park_agent_run(self, text: str, result) -> None:
        """Persist a directly-run agent goal that parked mid-flight.

        Without this the parked trace died with the turn: AERIS asked
        "…haan ya cancel?" but a following "haan" had nothing to resume.
        Stored as a blocked goal, the existing confirm flow (Step 2h)
        resumes it via ``goal_system.advance(approve_last=True)``.
        """
        try:
            from core import goal_system
            store = goal_system.get_goal_store()
            # Re-running the same blocked command must not pile up zombie
            # goals — drop older parked twins of this exact text first.
            for old in store.by_state("blocked"):
                if old.source == "agent" and old.text == text:
                    store.drop(old)
            g = goal_system.Goal(text=text, source="agent")
            g.scratchpad = goal_system.steps_to_scratch(result.steps)
            store.add(g)
            store.park(g, result.block_reason or "need_user",
                       ask=result.reply or "")
        except Exception as e:
            log.debug("[engine] agent park persist skipped: %s", e)

    # Cues that a request is more than a single action — worth the agent loop.
    _MULTISTEP_CUES = (
        " and then ", " and also ", " then ", " after that ", " aur phir ",
        " uske baad ", " uske bad ", " followed by ", ", then ", "; ",
        " karke ", " kar ke ", " karkay ",
    )

    def _looks_multistep(self, text: str) -> bool:
        """Cheap heuristic: does this utterance plausibly need several skills?"""
        if not text:
            return False
        low = f" {text.lower().strip()} "
        if any(cue in low for cue in self._MULTISTEP_CUES):
            return True
        # Two or more " and "-joined clauses, or an unusually long request.
        if low.count(" and ") + low.count(" aur ") >= 2:
            return True
        return len(text.split()) >= 14

    def _build_agent(self) -> AgentOrchestrator:
        """Wire the agentic loop onto the live LLM + tool router."""
        def llm_step(goal: str, scratchpad: list):
            # Continuity (Q1·M1): on the FIRST turn, recall what AERIS knows
            # about this goal from the Memory Fabric and hand it to the planner.
            # Only the first turn (empty scratchpad) so it doesn't re-inject
            # every step. Failure → plain goal (never blocks the loop).
            g = goal
            if not scratchpad:
                try:
                    from core import memory_fabric
                    ctx = memory_fabric.get_fabric().recall_context(goal, k=4)
                    if ctx:
                        g = f"{goal}\n\n{ctx}"
                except Exception as e:
                    log.debug("[engine] recall context skipped: %s", e)
            # Relevance-filtered tool menu (≤12) — the full ~400-tool
            # manifest drowns the embedded 1.5B model. Query = goal plus
            # the latest observation, so the menu adapts mid-plan
            # ("...phone pe bhejo" pulls bridge tools in for step 2).
            from core.tool_select import select_tools
            query = goal
            if scratchpad:
                query += " " + (getattr(scratchpad[-1], "observation", "") or "")
            try:
                top3 = self.brain.predict(goal, threshold=0.0).top3
            except Exception:
                top3 = []
            tools = select_tools(
                query, tools_manifest() + self._builtin_tools_manifest(),
                top_intents=top3)
            return self.llm.agent_step(
                goal=g,
                scratchpad=scratchpad,
                tools=tools,
                memory_facts=self.memory.all_facts(),
            )

        def run_tool(name: str, args: dict) -> str:
            # Reuse ToolRouter's single-call path (handles remember_fact,
            # executor dispatch, and error wrapping uniformly).
            return self.tool_router._run_one(name, args)

        # Q1·M3: govern every autonomous tool call by the Autonomy Ladder and
        # write it to the Ledger with a "why" (explainable + auditable). Wrapped
        # so a governance hiccup never stops the agent.
        authorize = record = None
        try:
            from core import autonomy
            gate = autonomy.get_gate()

            def authorize(name, args):  # noqa: F811
                return gate.authorize(name, autonomy.L3_ACT)

            def record(name, args, decision, why, result):  # noqa: F811
                gate.ledger.record(
                    action=name, args=args, cls=autonomy.classify(name),
                    level=autonomy.L3_ACT, decision=decision, why=why,
                    result=result)
        except Exception as e:
            log.debug("[engine] agent governance wiring skipped: %s", e)

        # Q3·M7 Reflexion: after every agent run, a critic distils a lesson from
        # the trace (esp. on failure) into Memory Fabric, so future planning
        # recalls "last time this kind of goal, X didn't work". Best-effort; the
        # local LLM only tidies the wording, never invents the verdict.
        def reflect(goal, result):  # noqa: F811
            from core import reflection
            reflection.learn(
                goal, result.steps, result.stopped_reason,
                llm=lambda p: (self.llm.reply(p, "neutral", {}, []) or ""))

        # No confirm callback yet → gate "confirm" decisions block by default
        # (safe: irreversible/over-budget acts won't run autonomously). A real
        # one-turn confirm flow can be wired later.
        return AgentOrchestrator(
            llm_step=llm_step, run_tool=run_tool,
            authorize=authorize, record=record, reflect=reflect)

    def _builtin_tools_manifest(self) -> list[dict]:
        """Tools backed by core/executor.py (not yet @skill-decorated)."""
        return [
            {"name": "open_app",        "description": "Launch a desktop application", "args": ["app_name"]},
            {"name": "close_app",       "description": "Kill a running application",   "args": ["app_name"]},
            {"name": "get_weather",     "description": "Stub weather (use real_weather if available)", "args": []},
            {"name": "get_time",        "description": "Current time and date",        "args": []},
            {"name": "take_screenshot", "description": "Capture screen to file",       "args": []},
            {"name": "search_web",      "description": "Google search a query",        "args": ["query"]},
            {"name": "play_youtube",    "description": "YouTube search a query",       "args": ["query"]},
            {"name": "open_website",    "description": "Open a URL in browser",        "args": ["url"]},
            {"name": "system_info",     "description": "Battery, CPU, RAM stats",      "args": []},
            {"name": "volume_up",       "description": "Increase system volume",       "args": []},
            {"name": "volume_down",     "description": "Decrease system volume",       "args": []},
            {"name": "volume_mute",     "description": "Mute system volume",           "args": []},
            {"name": "lock_screen",     "description": "Lock the workstation",         "args": []},
            {"name": "calculate",       "description": "Evaluate a math expression",   "args": ["expression"]},
            {"name": "create_note",     "description": "Save a timestamped text note", "args": ["content"]},
            {"name": "set_reminder",    "description": "Schedule a real reminder",     "args": ["message", "time"]},
            {"name": "schedule_meeting","description": "Schedule a meeting",           "args": ["person", "time"]},
        ]

    def _required_entities(self, intent: str) -> list:
        """Required slot names for an intent — intents.json first, then the
        @skill registry (same resolution order as StateManager)."""
        try:
            cfg = self.state.intents_data.get(intent)
            if cfg:
                return list(cfg.get("required_entities", []) or [])
        except Exception:
            pass
        try:
            from core.skill_registry import get_skill
            sk = get_skill(intent)
            return list(getattr(sk, "required_entities", []) or [])
        except Exception:
            return []

    def _render_state_result(self, result: str) -> Optional[str]:
        """Convert state_manager output (SUCCESS_EXECUTE|...|... or prompt) to spoken text."""
        if not result:
            return None
        if result.startswith("SUCCESS_EXECUTE|"):
            parts = result.split("|", 2)
            intent = parts[1]
            slots = json.loads(parts[2])
            # Irreversible skills don't run on the first ask — park them
            # behind a one-turn "pakka?" confirmation (confirm_gate).
            from core.confirm_gate import confirm_prompt, needs_confirmation
            if needs_confirmation(intent):
                self._pending_confirm = (intent, slots)
                return confirm_prompt(intent, slots)
            out = self.executor.execute(intent, slots)
            # Record the executed turn in dialogue context. This is the ONE
            # choke point every execution passes through (direct dispatch,
            # slot-fill completion, disambig answer), so follow-ups resolve
            # no matter which path ran the command.
            try:
                self.dialogue.note(intent, slots,
                                   slots.get("raw_text", ""), out or "")
            except Exception:
                pass
            return out
        return result  # clarification prompt or error string

    # ------------------------------------------------------------------ #
    #  Run loop                                                            #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        self._ensure_io()
        self._speak(f"{_settings.assistant_name()} systems online. Ready to help, sir.")

        while self.is_running:
            try:
                text = self._stt.listen()
                if not text:
                    time.sleep(0.3)
                    continue
                print(f"You: {text}")
                response = self.process_text(text)
                if response:
                    self._speak(response)
            except KeyboardInterrupt:
                self._speak("Shutting down. Goodbye, sir!")
                self.is_running = False
            except Exception as e:
                log.exception(f"Engine error: {e}")
                time.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    engine = JarvisMainEngine()
    engine.run()
