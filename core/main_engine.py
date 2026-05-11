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
import sys
import time
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import settings as _settings
from core.brain import JarvisBrain
from core.conversation import ConversationHistory
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
from core.utterance_parser import find_best_interpretation, split_into_segments

log = logging.getLogger(__name__)

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

        # Pending-feedback tracker: id of the most recent executed utterance
        # awaiting a one-turn-window correction signal.
        self._pending_utterance_id: Optional[int] = None
        self.is_running = True

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
        n_skills = discover_skills("skills")
        if self._verbose and n_skills:
            print(f"  Loaded {n_skills} plugin skills.")

        self.brain = JarvisBrain(lazy=True)
        yield ("NLU", "Loading sentence encoder", 12)
        self.brain.load_encoder()

        yield ("NLU", "Loading intent index", 32)
        self.brain.build_or_load_index()

        yield ("NLU", "Loading entity extractor + spaCy NER", 50)
        self.entity_extractor = EntityExtractor(
            entities_path=os.path.join(_ROOT, "data", "entities.json"),
            intents_path=os.path.join(_ROOT, "data", "intents.json"),
        )

        yield ("NLU", "Loading sentiment + memory", 65)
        self.sentiment = SentimentAnalyzer()
        self.memory = UserMemory(
            self._memory_path or os.path.join(_ROOT, "data", "user_memory.json"),
            passphrase=self._memory_passphrase,
        )
        self.history = ConversationHistory(max_turns=8)
        self.disambiguator = Disambiguator()

        yield ("MEM", "Attaching feedback DB + LLM client", 78)
        self.feedback = FeedbackStore(self._feedback_db_path
                                      or os.path.join(_ROOT, "data", "feedback_log.sqlite"))
        self.llm = LLMChat()

        yield ("SYS", "Wiring scheduler + state machine + executor", 90)
        self.scheduler = self._build_scheduler() if self._enable_scheduler else None
        self.state = StateManager()
        self.executor = ActionExecutor(scheduler=self.scheduler)
        self.tool_router = ToolRouter(executor=self.executor, memory=self.memory)

        yield ("SYS", "All modules nominal · brain ready", 100)

    def _build_scheduler(self):
        """Create the reminder scheduler if APScheduler is available."""
        try:
            from core.scheduler import ReminderScheduler
        except ImportError:
            return None

        def _on_fire(message: str) -> None:
            self._speak(f"Reminder, sir: {message}")

        try:
            return ReminderScheduler(_on_fire)
        except ImportError:
            return None

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

    def process_text(self, text: str) -> Optional[str]:
        """Run the full brain pipeline on a single utterance.

        Returns the assistant's response text, or None if the utterance was
        empty / silent. All side effects (state changes, DB writes, memory
        writes) happen inside.

        Multi-command utterances ("X aur Y") are split into segments and
        each segment runs through the brain pipeline independently. The
        responses are joined with newlines.
        """
        if not text or not text.strip():
            return None

        text = text.strip()

        # ── Step 0a: slot-filling in progress ──
        if self.state.is_waiting_slot():
            if _is_cancel(text):
                self.state.reset()
                return "Theek hai, cancel kar diya."
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

        # ── Step 1: pending feedback (within one-turn window) ──
        if self._pending_utterance_id is not None:
            if _is_correction(text):
                self.feedback.record_feedback(self._pending_utterance_id, "corrected")
                self._pending_utterance_id = None
                return "Sorry. Phir se batao kya karna hai?"
            # Any other input means the prior execution was implicitly accepted.
            self.feedback.record_feedback(self._pending_utterance_id, "accepted")
            self._pending_utterance_id = None

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

        # ── Step 3: cancel keyword with no live state ──
        if _is_cancel(text):
            return "Kuch chal nahi raha cancel karne ke liye, sir."

        # ── Step 4: split into segments and run pipeline per segment ──
        segments = split_into_segments(text)
        responses: list[str] = []
        for seg in segments:
            seg_response = self._process_segment(seg)
            if seg_response:
                responses.append(seg_response)

        if not responses:
            return None
        return "\n".join(responses)

    def _process_segment(self, text: str) -> Optional[str]:
        """Run brain prediction + execution on a single command segment.

        This is the per-segment version of the original pipeline tail
        (sentiment + brain + threshold + disambig + execute / fallback).
        Memory / state / cancel checks have already happened in
        process_text() against the full utterance.
        """
        if not text or not text.strip():
            return None

        # Sentiment is per-segment so a "weather batao aur tu bekaar hai"
        # response can pick up the negative tone of the second clause.
        sentiment = self.sentiment.classify(text)

        # Subspan scanner: tries the full segment plus a few trimmed
        # variants and picks the highest-confidence interpretation. This
        # is what lets "ek kam karo notepad open karo" be recognised as
        # open_app instead of volume_down ("kam karo" is filler here).
        # The winning_span is used ONLY for intent classification — entity
        # extraction still runs on the full segment so that app names /
        # urls / queries that live OUTSIDE the trimmed span aren't lost.
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

        intent_for_threshold = pred.intent or "_unknown"
        threshold = self.feedback.get_threshold(intent_for_threshold)

        self.history.add_user(text, sentiment.label)

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
            entities = self.entity_extractor.extract(text, pred.intent)
            result_str = self.state.process_prediction(
                [{"intent": pred.intent, "probability": f"{pred.confidence:.3f}"}],
                entities,
            )
            action = "executed" if result_str.startswith("SUCCESS_EXECUTE|") else "asked_slot"
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
            # User reply didn't disambiguate — abort gracefully.
            if utterance_id is not None:
                self.feedback.record_feedback(utterance_id, "cancelled")
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

        if llm_up and self._enable_tool_calls:
            tools = tools_manifest() + self._builtin_tools_manifest()
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
            reply = self.llm.reply(
                user_text=text,
                sentiment_label=sentiment.label,
                memory_facts=self.memory.all_facts(),
                history=self.history.as_messages(),
            )
            if reply:
                self.history.add_assistant(reply)
                return reply

        self.feedback.queue_low_confidence(utterance_id, text, pred.top3)
        msg = "Ye samajh nahi paaya, sir. Aap thoda clear bolenge?"
        self.history.add_assistant(msg)
        return msg

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

    def _render_state_result(self, result: str) -> Optional[str]:
        """Convert state_manager output (SUCCESS_EXECUTE|...|... or prompt) to spoken text."""
        if not result:
            return None
        if result.startswith("SUCCESS_EXECUTE|"):
            parts = result.split("|", 2)
            intent = parts[1]
            slots = json.loads(parts[2])
            return self.executor.execute(intent, slots)
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
