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

from core.brain import JarvisBrain
from core.conversation import ConversationHistory
from core.disambiguator import Disambiguator
from core.entity_extractor import EntityExtractor
from core.executor import ActionExecutor
from core.feedback import FeedbackStore
from core.llm_chat import LLMChat
from core.memory import UserMemory
from core.sentiment import SentimentAnalyzer
from core.state_manager import StateManager

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
                 verbose: bool = True):
        if verbose:
            print("Initialising A.E.R.I.S v3.2 (full brain stack)...")

        # Audio I/O — instantiated lazily in run() if not injected.
        # Keeping these optional makes the engine testable without pyaudio.
        self._stt = stt
        self._tts = tts

        # Brain stack
        self.brain = JarvisBrain()
        self.entity_extractor = EntityExtractor(
            entities_path=os.path.join(_ROOT, "data", "entities.json"),
            intents_path=os.path.join(_ROOT, "data", "intents.json"),
        )
        self.sentiment = SentimentAnalyzer()
        self.memory = UserMemory(memory_path
                                 or os.path.join(_ROOT, "data", "user_memory.json"))
        self.history = ConversationHistory(max_turns=8)
        self.disambiguator = Disambiguator()
        self.feedback = FeedbackStore(feedback_db_path
                                      or os.path.join(_ROOT, "data", "feedback_log.sqlite"))
        self.llm = LLMChat()

        # State + execution
        self.state = StateManager()
        self.executor = ActionExecutor()

        # Pending-feedback tracker: id of the most recent executed utterance
        # awaiting a one-turn-window correction signal.
        self._pending_utterance_id: Optional[int] = None

        self.is_running = True
        if verbose:
            print("A.E.R.I.S is online.")

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
            print(f"AERIS: {text}")
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
        # Recall must run before store, otherwise "mera naam kya hai" gets caught
        # by the name-store pattern as name="Kya Hai".
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

        # ── Step 4: sentiment ──
        sentiment = self.sentiment.classify(text)

        # ── Step 5: brain (raw, threshold=0 — we judge per-intent below) ──
        pred = self.brain.predict(text, threshold=0.0)

        # ── Step 6: per-intent learned threshold (the bandit policy) ──
        intent_for_threshold = pred.intent or "_unknown"
        threshold = self.feedback.get_threshold(intent_for_threshold)

        self.history.add_user(text, sentiment.label)

        if pred.intent and pred.confidence >= threshold:
            # 6a. close call?
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

            # 6b. execute
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

        # ── Step 7: low confidence → LLM chit-chat or rejection ──
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
        action = "chat_fallback" if self.llm.is_available() else "rejected"
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

        if self.llm.is_available():
            reply = self.llm.reply(
                user_text=text,
                sentiment_label=sentiment.label,
                memory_facts=self.memory.all_facts(),
                history=self.history.as_messages(),
            )
            if reply:
                self.history.add_assistant(reply)
                return reply

        # No LLM (or LLM failed): queue as a learning candidate.
        self.feedback.queue_low_confidence(utterance_id, text, pred.top3)
        msg = "Ye samajh nahi paaya, sir. Aap thoda clear bolenge?"
        self.history.add_assistant(msg)
        return msg

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
        self._speak("AERIS systems online. Ready to help, sir.")

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
