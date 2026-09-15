"""JarvisBrain — combined neural + k-NN intent router.

Architecture
------------
Two classifiers live side-by-side:

1. ``NeuralIntentClassifier`` (fine-tuned XLM-R, ``core/intent_model.py``).
   Loaded only when a trained model exists at ``data/models/intent_neural/``
   AND its saved ``intents_hash`` matches the live ``intents.json``. Primary
   router when present — it understands paraphrase, code-mix, and word order
   variation that pure k-NN cosine misses.

2. ``IntentClassifier`` (sentence-encoder + k-NN, ``core/intent_classifier.py``).
   Always loaded — the safety net. Used:
     - when no neural model is trained yet (clean install, no breakage),
     - when the neural model's confidence is below the per-intent threshold,
     - as a top-3 enrichment source so the disambiguator sees nearest
       neighbours the neural classifier may not have considered.

Both expose ``predict(text) -> Prediction``; the orchestration here decides
which result to surface and how the top-3 is merged.

Retrain workflow
----------------
    python -m core.train_intent

After it finishes, restart AERIS. The brain detects the new model,
verifies its hash matches the live intents.json, and switches over.
If you edit intents.json *without* retraining, the hash mismatch flips
the brain back to pure k-NN until you retrain.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Optional

from core.intent_classifier import IntentClassifier, Prediction
from core.intent_model import NeuralIntentClassifier

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Confidence below this → neural is "unsure", we cross-check k-NN.
# Soft floor; the feedback bandit's per-intent threshold (feedback.py)
# is the authoritative gate downstream.
_NEURAL_LOW_CONF = 0.55

# Idle-unload: if no predict() in this many seconds AND resource pressure
# is at least WARNING, drop the in-RAM encoder + neural model. Reloads
# transparently on the next predict() (with a noticeable ~3s latency the
# user will see exactly once, then the model stays hot until idle again).
_IDLE_UNLOAD_S = 5 * 60


def _idle_unload_seconds() -> float:
    """Idle window before model weights are dropped.

    ``AERIS_IDLE_UNLOAD_S`` overrides the 5-minute default; ``0`` disables the
    unloader entirely (weights stay hot for the life of the process). A
    garbage value falls back to the default rather than breaking boot.
    """
    raw = os.environ.get("AERIS_IDLE_UNLOAD_S")
    if raw is None or not str(raw).strip():
        return float(_IDLE_UNLOAD_S)
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        log.warning("[Brain] bad AERIS_IDLE_UNLOAD_S=%r — using %ss",
                    raw, _IDLE_UNLOAD_S)
        return float(_IDLE_UNLOAD_S)

# Prediction LRU — repeated phrases (e.g. "open chrome" tapped twice)
# skip the encoder + neural model entirely. Size kept small (256) so the
# cache never holds enough to bias the resource-pressure heuristics.
_PREDICT_CACHE_SIZE = 256


# ── Deterministic arithmetic pre-router ──────────────────────────────────
# A bare arithmetic expression ("12 plus 37 kitna hai", "144 divided by 12",
# "18 ka 20 percent") must route to the general `calculate` intent, NOT to one
# of the 100+ specialised formula skills (gcd_lcm / log_calc / gst_calc) that
# the k-NN otherwise picks off the bloated calculator corpus. Structural
# evidence (≥2 numbers + an operator, no domain word) beats the cosine vote —
# same principle as main_engine's gazetteer override. Measured: `calculate`
# routed 0% correctly before this. See docs/ROUTING_ACCURACY_AUDIT.md.
import re as _re

# Symbol operators must be space-flanked so date/hyphen tokens ("2026-08-01",
# "covid-19") never read as subtraction; word operators are safe unflanked.
_ARITH_OP = _re.compile(
    r"\s[+\-*/×÷]\s|\b(plus|minus|into|times|multiply|multiplied|divided|"
    r"divide|add|added|subtract|power|percent|percentage|guna|jodo|ghatao)\b",
    _re.I)
# Domain words → a specialised skill is genuinely the right owner; don't steal.
_ARITH_EXCLUDE = _re.compile(
    r"\b(tip|gst|tax|vat|emi|loan|interest|discount|bmi|gcd|lcm|hcf|area|"
    r"perimeter|circumference|prime|factorial|fibonacci|roman|binary|hex|"
    r"octal|celsius|fahrenheit|ratio|compound)\b", _re.I)
_ARITH_NUM = _re.compile(r"\d+(?:\.\d+)?")


def _is_plain_arithmetic(text: str) -> bool:
    """True for a clear two-operand arithmetic expression that belongs to
    `calculate` (conservative: needs ≥2 numbers + an operator, short, and no
    specialised-domain word)."""
    if not text:
        return False
    t = text.strip()
    if len(t) > 60 or _ARITH_EXCLUDE.search(t):
        return False
    if len(_ARITH_NUM.findall(t)) < 2:
        return False
    return bool(_ARITH_OP.search(t))


# ── Command anchors ──────────────────────────────────────────────────────
# Unambiguous phrasings that must deterministically hit a core intent, before
# k-NN can mis-route them among 587 candidates (measured harmful mis-routes:
# get_time→change_log/voice_faster, search_web→full_system_health). Each entry:
# (signal, exclude, intent). Fires only when signal matches AND exclude does
# not — so adjacent skills (world_time, reading_time, weather) stay untouched.
# Conservative on purpose; extend as more harmful mis-routes are measured.
# These built-ins are always active; users can ADD more (no code, no retrain) in
# data/routing_anchors.json — see _load_user_anchors below.
_BUILTIN_ANCHORS = [
    (_re.compile(r"\b(kitne?\s+baje|kya\s+time\b|time\s+kya|samay\s+kya|"
                 r"what\s+time\s+is|what'?s?\s+the\s+time|abhi\s+.*time|"
                 r"current\s+time|time\s+(bata|batao|bol|bolo|dikha|dikhao|"
                 r"dekh|dekho|check)|clock)\b", _re.I),
     _re.compile(r"\b(reading|world|zone|timezone|until|travel|over\s*time|"
                 r"alarm|timer|set|reminder|meeting|schedule)\b", _re.I),
     "get_time"),
    (_re.compile(r"\b(google\s+(kar|kro|karo|it)|search\s+(kar|kro|karo|the\s+web|for)|"
                 r"web\s+pe|internet\s+pe|dhoond|dhund|khoj|look\s+up)\b", _re.I),
     _re.compile(r"\b(file|files|setting|youtube|tab\b|weather|mausam)\b", _re.I),
     "search_web"),
    # word definition ("matlab batao X", "meaning of X", "X ka matlab", "define X")
    (_re.compile(r"\b(matlab|meaning|define|definition|arth|shabd\s+ka|word\s+meaning)\b", _re.I),
     _re.compile(r"\b(life\s+ka\s+matlab|zindagi|is\s+baat\s+ka|meeting|explain\s+(this|code|the\s+process))\b", _re.I),
     "define_word"),
    # gcd/lcm/hcf → gcd_lcm (was mis-routing to set_timer and CREATING a timer!)
    (_re.compile(r"\b(gcd|lcm|hcf)\b", _re.I),
     _re.compile(r"\b(timer|alarm|remind|remove|delete)\b", _re.I),
     "gcd_lcm"),
    # is-N-prime / factors / even-odd → number_properties (was → a days-from-now
    # skill: "is 29 prime" answered "29 din baad …"). Digit-anchored so
    # "prime minister" / "factors of production" never match.
    (_re.compile(r"\bfactors\s+of\s+\d|\bis\s+\d+\s+prime|\b\d+\s+prime\b|\beven\s+or\s+odd\b", _re.I),
     _re.compile(r"\bminister\b", _re.I),
     "number_properties"),
    # text case/reverse ops → text_transform (was mis-routing to GREETING when the
    # data word was "hello"/"hi": "uppercase karo hello" → "Good morning!").
    (_re.compile(r"\b(uppercase|lowercase|upper\s*case|lower\s*case|reverse|"
                 r"title\s*case|capitalize|ulta\s+kar)\b", _re.I),
     # exclude clipboard (→ clipboard_transform anchor) + number-reverse/undo.
     _re.compile(r"\breverse\s+(the\s+)?number|\bundo\b|reverse\s+engineer|"
                 r"\bclip(board)?\b", _re.I),
     "text_transform"),
    # count characters/letters → count_chars (was → greeting when the text was
    # "hello"). NOTE: deliberately NOT "length of" — too ambiguous ("length of
    # the meeting" is a duration, not a char count).
    (_re.compile(r"\bcount\s+(characters|letters|char)\b|"
                 r"\bkitne\s+(letters|characters|char)\b", _re.I),
     _re.compile(r"\bword\s+count\b", _re.I),
     "count_chars"),
    # identity questions → who_are_you (were scattering to whoami/prefs/KG).
    # Excludes "my name" (the USER's name → get_preference).
    (_re.compile(r"\bwho\s+are\s+you\b|\bwhat\s+are\s+you\b|"
                 r"\bwhat(?:'?s|\s+is)?\s+your\s+name\b|\byour\s+name\s+kya\b|"
                 r"\btumhara\s+naam\b|\btera\s+naam\b|\baap\s+kaun\b|\btum\s+kaun\b|"
                 r"\b(about|introduce)\s+yourself\b|\bwho\s+is\s+aeris\b|"
                 r"\btum\s+kya\s+ho\b|\bapne\s+bare\s+me\b", _re.I),
     _re.compile(r"\bmy\s+name\b|\byour\s+(favou?rite|opinion|age|number)\b|"
                 r"\bgonna\b|\bgoing\s+to\b", _re.I),
     "who_are_you"),
    # system resource queries → system_stats (were mis-routing to calculate/
    # quick_math on the "kitna hai" cue: "cpu usage kitna hai" → "Kya calculate?").
    (_re.compile(r"\b(cpu\s+(usage|load)|ram\s+usage|memory\s+usage|"
                 r"disk\s+(space|usage)|storage\s+(free|space))\b", _re.I),
     _re.compile(r"\bfree\s+up|\bclean(up)?\b|\bempty\b", _re.I),
     "system_stats"),
    # time-unit CONVERSION → unit_convert (was mis-routing to set_timer). Needs
    # TWO time units + in/to, so "5 minute ka timer" (a real timer) is untouched.
    (_re.compile(r"\b\d+(?:\.\d+)?\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?|"
                 r"days?|weeks?|years?)\s+(in|to|into|me)\s+(hours?|minutes?|"
                 r"seconds?|days?|weeks?|years?|hrs?|mins?|secs?)\b", _re.I),
     _re.compile(r"\b(timer|alarm|reminder|ka\s+timer|remind\s+me)\b", _re.I),
     "unit_convert"),
    # number base conversion → base_convert (was mis-routing badly: "42 to
    # binary" answered "42 din baad"!). Hex left to the codec/number handler.
    (_re.compile(r"\b(to|in|into)\s+(binary|octal|decimal)\b|"
                 r"\b(binary|octal|decimal)\s+of\s+\d", _re.I),
     _re.compile(r"\breminder\b|\btimer\b|\bcode\s+the\b", _re.I),
     "base_convert"),
    # generate a uuid → uuid_generate (was → repeat_last).
    (_re.compile(r"\b(generate|banao|de|do)\s+(a\s+|ek\s+)?uuid\b|"
                 r"\buuid\s+(generate|banao|do|chahiye)\b|\bnew\s+uuid\b", _re.I),
     _re.compile(r"(?!x)x", _re.I),
     "uuid_generate"),
    # clipboard TRANSFORM → clipboard_transform (was → inline text_transform,
    # which transformed the WORD "clipboard", not the clipboard CONTENT).
    (_re.compile(r"\bclip(?:board)?\s+(?:me\s+|ko\s+)?(uppercase|upper\s*case|"
                 r"lowercase|lower\s*case|reverse|ulta|slug|strip|trim|"
                 r"title\s*case)\b", _re.I),
     _re.compile(r"(?!x)x", _re.I),
     "clipboard_transform"),
    # "what's in the clipboard" → clipboard_paste (show contents).
    (_re.compile(r"\bclipboard\s+(me\s+kya|content|text|kya\s+hai|dikhao|show)\b|"
                 r"\bwhat'?s?\s+(in\s+)?(the\s+)?clipboard\b|"
                 r"\bpaste\s+(the\s+)?clipboard\b", _re.I),
     _re.compile(r"\b(clear|wipe|history|transform|upper|lower|reverse)\b", _re.I),
     "clipboard_paste"),
    # find a file → file_search. Postfix Hinglish "<name> file kahaan hai" was
    # mis-routing (e.g. "productivity file kahaan hai" → a currency conversion!).
    # Requires the word "file(s)" so "office kahaan hai" (a place) is untouched.
    # Excludes open/delete/save verbs — "file kholo"/"file delete karo" aren't
    # searches. The handler recovers the name from raw_text (_fs_query).
    (_re.compile(r"\bfiles?\s+(kahaan|kahan|kaha)\s+hai\b|"
                 r"\b(kahaan|kahan)\s+hai\s+(\w+\s+){0,3}files?\b|"
                 r"\b(locate|find)\s+(the\s+|a\s+|my\s+)?files?\b|"
                 r"\bfiles?\s+(dhundo|dhoondo|dhundho|khojo|search\s+karo)\b", _re.I),
     _re.compile(r"\b(open|kholo|khol\s+do|delete|hata|create|banao|save|"
                 r"move|copy|rename|band\s+karo)\b", _re.I),
     "file_search"),
    # "kill <name>" → kill_process (was mis-routing to file_search: "kill zzqqxx"
    # searched for a file). SURGICAL — only the explicit English "kill X" form,
    # not "band karo"/"close" (those legitimately overlap close_app/stop_music).
    # Idioms ("kill time", "kill the lights/music/mood") are excluded; the handler
    # is defensive (blocks system procs, "no process found" on a typo) so a rare
    # mis-fire is harmless. Requires a 3+ char target after "kill".
    (_re.compile(r"\bkill\s+(?:the\s+)?[a-z][\w.\-]{2,}\b", _re.I),
     _re.compile(r"\bkill\s+(?:the\s+)?(time|it|him|her|them|me|us|switch|"
                 r"lights?|music|sound|noise|mood|vibe|engine|pain|deal|beat|"
                 r"buzz|power|joy|game|shot|two\s+birds|process$)\b", _re.I),
     "kill_process"),
    # Entertainment / conversational intents — a clear keyword must reach the
    # (already LLM-backed) skill, not scatter to play_music(!), current_time,
    # keep_awake_on, create_note or system_stats. These EXPECTED targets are the
    # real skills (not stubs), so anchoring lifts the metric too. Ordered
    # tell_joke, tell_story, motivate_me so "motivational story" → tell_story
    # (story wins over the motivate cue) and "funny joke" → tell_joke.
    (_re.compile(r"\b(joke|jokes|chutkula|chutkule|chutkla|pun)\b|"
                 r"\bpj\s+(suna|sunao|bol|bolo)\b", _re.I),
     _re.compile(r"\bpractical\s+joke\b", _re.I),
     "tell_joke"),
    (_re.compile(r"\b(story|stories|kahani|kahaani|kahaniya|kahini)\b", _re.I),
     _re.compile(r"\b(success|news|insta(gram)?|whatsapp|status|cover|life)\s+stor|"
                 r"\bstory\s+(dekho|dekh|dalo|daal|post|upload|status|check)\b", _re.I),
     "tell_story"),
    (_re.compile(r"\bmotivat|\bpep\s+talk|\bmood\s+(theek|thik|acha|better|sahi)\b|"
                 r"\bcheer\s+me\s+up|\bmann\s+nahi\s+lag|\bhaar\s+(maan|man)|"
                 r"\buplift", _re.I),
     _re.compile(r"(?!x)x", _re.I),
     "motivate_me"),
    # Volume + music core actions — clear keyword, but the WORST kind of mis-route:
    # opposite direction ("volume tez"→volume_mute, "awaaz dheemi"→volume_up) or
    # absurd ("gaana suna do"→create_note). up/down/mute are opposites so the
    # MODIFIER disambiguates. Order: mute (most specific) → up → down → play.
    (_re.compile(r"\bmute\b|\bchup\s+(kar|karo|ho\s+ja)|"
                 r"\b(awaaz|aawaz|awaz|sound|volume|audio)\s+(band|off|gayab|silent|mute)\b",
                 _re.I),
     _re.compile(r"\b(music|gaana|gana|song|video)\s+band\b", _re.I),
     "volume_mute"),
    (_re.compile(r"\b(volume|awaaz|aawaz|awaz|sound|audio)\s+(thoda\s+)?"
                 r"(tez|zyada|jyada|badha\w*|upar|up|high|loud)\b|"
                 r"\b(louder|turn\s+it\s+up|volume\s+up)\b", _re.I),
     _re.compile(r"(?!x)x", _re.I),
     "volume_up"),
    (_re.compile(r"\b(volume|awaaz|aawaz|awaz|sound|audio)\s+(thoda\s+)?"
                 r"(kam|dheem\w*|dheere|neeche|down|low|ghata\w*|reduce)\b|"
                 r"\b(quieter|turn\s+it\s+down|volume\s+down|make\s+it\s+quiet\w*)\b|"
                 r"\b(kam|dheere)\s+karo\s+(awaaz|volume|sound)\b", _re.I),
     _re.compile(r"(?!x)x", _re.I),
     "volume_down"),
    (_re.compile(r"\b(gaana|gana|gaane|gane|song|songs|music|track)\s+"
                 r"(bajao|baja|lagao|laga|play|suna|sunao|start|chalao|chala|dedo|de\s+do)\b",
                 _re.I),
     _re.compile(r"\b(band\s+kar|rok\s+do|stop|pause|mute)\b", _re.I),
     "play_music"),
    # "what can you do" / "kya kya kar sakte ho" / "mere jarvis mein kya hai" →
    # help_catalog (the capability overview). Users ask this a LOT and it was
    # scattering. Excludes "help me <do X>" (that's a real task, not the catalog).
    (_re.compile(r"\bwhat\s+can\s+(you|u|i)\s+(do|ask)\b|"
                 r"\bkya\s+kya\s+(kar\s+sakte|kaam\s+kar|aata|seekha)\b|"
                 r"\bkya\s+kar\s+sakte\s+(ho|hai)\b|"
                 r"\b(commands?|abilities|features|skills)\s+(kya\s+)?"
                 r"(list|dikhao|dikha|batao|bata|kaunsi|kaunse|konse|hain|hai)\b|"
                 r"\blist\s+(commands?|skills|abilities)\b|\bmere\s+jarvis\s+m|"
                 r"\bsab\s+kuch\s+(kya|batao|kar)\b|\btumhare\s+paas\s+kya\b|"
                 r"\bshow\s+(me\s+)?(your\s+|all\s+)?(commands|skills|abilities)\b|\bhelp\b|"
                 # "<category> commands/skills" → catalog drill-down
                 r"\b(system|math|maths|voice|vision|web|memory|clipboard|text|"
                 r"developer|media|music|productivity|apps|document|network|fun|"
                 r"finance|calculator|automation|personalization)\s+"
                 r"(commands?|skills|abilities)\b", _re.I),
     _re.compile(r"\bhelp\s+me\s+(open|close|find|write|calculat|set|send|play|"
                 r"call|band|khol|likh|khoj|dhund|remind|book)\b", _re.I),
     "help_catalog"),
]


def _load_user_anchors():
    """Load extra routing anchors from data/routing_anchors.json so a user can
    fix a mis-route WITHOUT touching code or retraining. Each entry:
        {"signal": "<regex>", "intent": "<intent>", "exclude": "<regex?>"}
    ``exclude`` is optional. Any bad entry/file is skipped, never fatal."""
    import json
    path = os.path.join(_ROOT, "data", "routing_anchors.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        rows = data.get("anchors", []) if isinstance(data, dict) else data
        out = []
        for a in rows or []:
            try:
                sig, intent = a.get("signal"), a.get("intent")
                if not sig or not intent:
                    continue
                excl = a.get("exclude") or r"(?!x)x"   # never matches
                out.append((_re.compile(sig, _re.I), _re.compile(excl, _re.I),
                            str(intent)))
            except Exception as ie:
                log.warning("[brain] skipping bad routing anchor %r: %s", a, ie)
        if out:
            log.info("[brain] loaded %d user routing anchor(s)", len(out))
        return out
    except Exception as e:
        log.warning("[brain] routing_anchors.json load failed: %s", e)
        return []


# Built-in anchors first (proven), then user additions.
_ANCHORS = _BUILTIN_ANCHORS + _load_user_anchors()


def _anchor_intent(text: str):
    """Return the deterministically-anchored intent for `text`, or None."""
    if not text:
        return None
    for sig, excl, intent in _ANCHORS:
        if sig.search(text) and not excl.search(text):
            return intent
    return None


class JarvisBrain:
    def __init__(self, *, lazy: bool = False):
        log.info("[Brain] Initialising...")
        self.classifier = IntentClassifier(
            intents_path=os.path.join(_ROOT, "data", "intents.json"),
            models_dir=os.path.join(_ROOT, "data", "models"),
            lazy=True,
        )
        self.neural = NeuralIntentClassifier(
            intents_path=os.path.join(_ROOT, "data", "intents.json"),
        )
        self._neural_active = False

        # Idle-unload bookkeeping. ``_last_predict_ts`` is the wall-clock
        # of the most recent predict() call; the ResourceMonitor pressure
        # callback consults it before unloading.
        self._last_predict_ts: float = time.monotonic()
        self._unload_lock = threading.RLock()
        self._encoder_loaded = False
        self._neural_loaded = False
        self._idle_unload_s = _idle_unload_seconds()
        # Idle-unload ticker state (see start_idle_unloader).
        self._unloader_thread: Optional[threading.Thread] = None
        self._unloader_stop: Optional[threading.Event] = None
        # Callbacks fired the first time the heavy models land in RAM — lets
        # lite boot defer encoder-dependent extras (chat gate, spaCy) and
        # still switch them on the moment the encoder actually arrives.
        self._ml_loaded_hooks: list = []
        # Extra resources the idle-unloader should sweep (spaCy, local LLM).
        # See add_idle_unload_hook.
        self._idle_unload_hooks: list = []

        # Prediction LRU keyed by (normalised_text, threshold). Invalidated
        # by clear_prediction_cache() — called after the classifier rebuilds
        # so stale results don't outlive an intents.json edit.
        self._pred_cache: "OrderedDict[tuple, Prediction]" = OrderedDict()
        self._pred_cache_lock = threading.Lock()

        if not lazy:
            self.load_encoder()
            self.load_neural_model()
            self.build_or_load_index()
            log.info("[Brain] Ready.")

    # ------------------------------------------------------------------ #
    #  Three-phase boot (mirrors IntentClassifier so the GUI can paint   #
    #  progress between chunks)                                            #
    # ------------------------------------------------------------------ #

    def prepare_fast_tiers(self) -> None:
        """Tier-0 boot — make the cheap router tiers usable with NO ML loaded.

        Builds only the verbatim pattern table (plain JSON + dict). After this
        call ``predict()`` can already answer every exact-match / arithmetic /
        anchor utterance; the encoder and neural head stay unloaded until an
        utterance misses all of them. This is what "lite" boot runs instead of
        ``load_encoder`` + ``load_neural_model`` + ``build_or_load_index``.
        """
        self.classifier.load_exact_only()

    def add_ml_loaded_hook(self, fn) -> None:
        """Register ``fn()`` to run right after the heavy models first land in
        RAM (cold load or reload-after-idle-unload). Used by the engine to
        warm the encoder-dependent extras — chat gate, spaCy NER — that lite
        boot skipped, so behaviour converges to the eager path once ML is up.
        Hooks are best-effort: an exception is logged, never raised.
        """
        self._ml_loaded_hooks.append(fn)

    def _fire_ml_loaded_hooks(self) -> None:
        for fn in list(self._ml_loaded_hooks):
            try:
                fn()
            except Exception as e:
                log.warning("[Brain] ml-loaded hook %r failed: %s", fn, e)

    @property
    def ml_loaded(self) -> bool:
        """True once the encoder is in RAM (i.e. the heavy tier is warm)."""
        return self._encoder_loaded

    def load_encoder(self) -> None:
        """Phase A1 — sentence encoder only.

        Split from neural-model load so the boot pipeline can yield progress
        between the two heavy loads (sentence-transformers ~5-10s + neural
        transformer ~5-10s would otherwise look like one ~17s freeze on the
        progress bar).
        """
        with self._unload_lock:
            self.classifier.load_encoder()
            self._encoder_loaded = True

    def load_neural_model(self) -> None:
        """Phase A2 — load the fine-tuned neural intent classifier if present.

        Safe to call even when no model is on disk or its hash has drifted —
        the brain just stays on the k-NN router in that case.
        """
        with self._unload_lock:
            if self.neural.is_trained():
                log.info("[Brain] Trained neural classifier present; loading...")
                if self.neural.load():
                    self._neural_active = True
                    self._neural_loaded = True
                    log.info("[Brain] Neural classifier ACTIVE (primary router).")
                else:
                    log.warning("[Brain] Neural load failed — falling back to k-NN only.")
            elif self.neural.is_present():
                log.info("[Brain] Neural model on disk but intents.json hash drifted — "
                         "using k-NN. Run `python -m core.retrain` to refresh.")
                self._log_pending_learning()
            else:
                log.info("[Brain] No neural model yet — using k-NN. "
                         "Train one with `python -m core.retrain`.")

    @staticmethod
    def _log_pending_learning() -> None:
        """Boot-time retrain advisor: surface how much harvested knowledge is
        waiting whenever the brain boots in fallback mode. Log-only; never
        blocks or raises."""
        try:
            from core.learning_loop import LearningStore
            s = LearningStore().status()
            if s["new_since_last_train"]:
                log.info("[Brain] %d learned sample(s) waiting for the next "
                         "retrain (%d in review).",
                         s["new_since_last_train"], s["review_samples"])
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Idle-unload (Phase 3b — lazy paging of large model weights)        #
    # ------------------------------------------------------------------ #

    def try_unload_idle(self) -> bool:
        """Drop encoder + neural model from RAM if idle long enough.

        Returns True if anything was unloaded. Safe to call from any
        thread (locked). The next ``predict()`` will transparently
        reload, costing ~3s of latency exactly once.
        """
        # ENCODER_LOCK (outer) so freeing the encoder's tensors can NEVER
        # overlap an in-flight encode on another thread — a concurrent free +
        # torch forward is a use-after-free → Windows heap corruption 0xC0000374.
        # _unload_lock stays as the inner idle-state guard. Lock order is
        # always ENCODER_LOCK → _unload_lock (matches _ensure_loaded) so no
        # deadlock. ENCODER_LOCK is an RLock → re-entry from predict is safe.
        from core.encoder_lock import ENCODER_LOCK
        with ENCODER_LOCK, self._unload_lock:
            idle_for = time.monotonic() - self._last_predict_ts
            if idle_for < self._idle_unload_s:
                return False
            if not (self._encoder_loaded or self._neural_loaded):
                return False
            log.info("[Brain] idle %.0fs → unloading models to reclaim RAM",
                     idle_for)
            # Drop the SentenceTransformer + sklearn index — keep the
            # labels so we can rebuild quickly. The objects become
            # garbage; Python's GC reclaims their tensors.
            try:
                self.classifier.encoder = None
                self.classifier.nn = None
                self.classifier.embeddings = None
                self._encoder_loaded = False
            except Exception:
                pass
            try:
                self.neural.model = None
                self.neural.tokenizer = None
                self._neural_loaded = False
                self._neural_active = False
            except Exception:
                pass
            # Hint the allocator to give pages back to the OS.
            import gc
            gc.collect()
            return True

    # ------------------------------------------------------------------ #
    #  Idle-unload TICKER — the other half of load-free                   #
    # ------------------------------------------------------------------ #
    #
    # `try_unload_idle()` has existed for a while but nothing ever called it
    # on a timer: its only caller was the GUI's ResourceMonitor *pressure*
    # callback, i.e. it fired only once the whole machine was already short
    # on memory. So after one utterance that reached the encoder, AERIS held
    # ~800 MB of weights forever, even sitting untouched overnight. (And in
    # split-brain mode that callback couldn't reach the brain at all — it
    # looks up `self._brain._engine`, which a RemoteBrain doesn't have.)
    #
    # Running the ticker inside JarvisBrain fixes both at once: the in-process
    # engine and the split child each own one, no GUI and no cross-process
    # plumbing involved. Paired with lite boot the memory curve becomes
    # "~105 MB → ~900 MB while you're actually talking to it → ~105 MB again".

    def add_idle_unload_hook(self, fn) -> None:
        """Register ``fn() -> bool`` to run on every idle-unloader tick.

        The brain only owns the encoder and the neural head, but they are not
        the only weights in the process: spaCy (~220 MB, pulled in with torch)
        and the local Qwen LLM (a 1 GB gguf) are both loaded on demand and
        were never released — `LocalLLM.maybe_unload_idle()` even existed,
        documented, with *zero callers*. Rather than teach JarvisBrain about
        resources the engine owns, the engine registers a hook per resource
        and the ticker sweeps them.

        Return True if the hook actually freed something (for logging). Hook
        failures are logged, never raised — a stuck unloader must not end
        idle-unloading for the session.
        """
        self._idle_unload_hooks.append(fn)

    def _sweep_idle_hooks(self) -> None:
        for fn in list(self._idle_unload_hooks):
            try:
                if fn():
                    log.info("[Brain] idle-unloader hook %s freed resources",
                             getattr(fn, "__name__", fn))
            except Exception as e:
                log.warning("[Brain] idle-unload hook %r failed: %s", fn, e)

    def start_idle_unloader(self, interval_s: Optional[float] = None) -> bool:
        """Start the background thread that unloads idle model weights.

        Idempotent — returns False if one is already running or the feature is
        disabled. Set ``AERIS_IDLE_UNLOAD_S=0`` to disable, or to any number of
        seconds to override the 5-minute default idle window.

        ``interval_s`` is how often to CHECK, and defaults to half the idle
        window (capped to 5..60 s) rather than a flat 60 s — otherwise a short
        window is silently rounded up to the check interval, and someone who
        asks for a 30 s window waits 60-90 s for their RAM back.
        """
        if getattr(self, "_unloader_thread", None) is not None:
            return False
        if self._idle_unload_s <= 0:
            log.info("[Brain] idle-unloader disabled (idle window <= 0)")
            return False
        if interval_s is None:
            interval_s = max(5.0, min(60.0, self._idle_unload_s / 2.0))

        self._unloader_stop = threading.Event()

        def _loop():
            while not self._unloader_stop.wait(interval_s):
                try:
                    if self.try_unload_idle():
                        log.info("[Brain] idle-unloader reclaimed model weights")
                except Exception as e:            # never kill the thread
                    log.warning("[Brain] idle-unloader tick failed: %s", e)
                self._sweep_idle_hooks()

        t = threading.Thread(target=_loop, name="BrainIdleUnloader", daemon=True)
        self._unloader_thread = t
        t.start()
        log.info("[Brain] idle-unloader started (unload after %.0fs idle, "
                 "checked every %.0fs)", self._idle_unload_s, interval_s)
        return True

    def stop_idle_unloader(self) -> None:
        """Stop the ticker. Safe to call when it was never started."""
        stop = getattr(self, "_unloader_stop", None)
        if stop is not None:
            stop.set()
        self._unloader_thread = None

    def _ensure_loaded(self) -> None:
        """Reload encoder + neural model if a previous idle-unload dropped them."""
        # Same lock order as try_unload_idle: ENCODER_LOCK (outer) so a reload
        # that swaps in fresh encoder objects can't overlap a concurrent encode.
        from core.encoder_lock import ENCODER_LOCK
        warmed = False
        with ENCODER_LOCK, self._unload_lock:
            if not self._encoder_loaded:
                log.info("[Brain] cold predict — reloading encoder")
                self.classifier.load_encoder()
                self.classifier.build_or_load_index()
                self._encoder_loaded = True
                warmed = True
            if not self._neural_loaded and self.neural.is_trained():
                log.info("[Brain] cold predict — reloading neural model")
                if self.neural.load():
                    self._neural_loaded = True
                    self._neural_active = True
                    warmed = True
        # Hooks run OUTSIDE the locks: they load spaCy / fit the chat gate,
        # which itself encodes through ENCODER_LOCK (an RLock, but the hook
        # may hand work to another thread — don't hold locks across it).
        if warmed:
            self._fire_ml_loaded_hooks()

    def build_or_load_index(self) -> None:
        """Phase B — k-NN index cache load or rebuild."""
        self.classifier.build_or_load_index()

    # ------------------------------------------------------------------ #
    #  Predict                                                            #
    # ------------------------------------------------------------------ #

    def predict(self, text: str, threshold: float = 0.5) -> Prediction:
        """Combined neural-first / k-NN-fallback prediction.

        Rules:
          * No trained neural model → pure k-NN.
          * Neural confidence ≥ _NEURAL_LOW_CONF → trust neural. Merge
            its top3 with k-NN's top-1 (if a different intent) so the
            disambiguator gets the broader picture.
          * Neural confidence < _NEURAL_LOW_CONF → defer to k-NN, but
            merge neural's top-1 into the surfaced top3 as a second
            opinion for the disambiguator.
        """
        # TIERED ROUTER (docs/AERIS_LOADFREE_ARCHITECTURE_AND_ROADMAP.md §3.3).
        # Tiers 0-2 below (LRU cache → exact pattern → arithmetic → anchors)
        # are pure string/regex work. They run FIRST, before `_ensure_loaded`,
        # so an utterance they can answer never loads the sentence encoder or
        # the neural head at all. `_ensure_loaded()` is deferred to the k-NN /
        # neural tier — the only place that actually needs weights in RAM.
        # (It used to sit here at the top, which meant every turn — including
        # a verbatim "notepad kholo" — paid the full torch load.)
        self._last_predict_ts = time.monotonic()

        normalized = self.classifier.normalizer.clean(text) if text else ""
        cache_key = (normalized, threshold)

        # LRU short-circuit for repeated queries.
        with self._pred_cache_lock:
            cached = self._pred_cache.get(cache_key)
            if cached is not None:
                self._pred_cache.move_to_end(cache_key)
                return cached

        # Exact-pattern fast path. Verbatim user phrases that match a
        # known pattern bypass both classifiers — guards against the
        # neural model overruling a freshly-added pattern (e.g. "open
        # notepad" → open_app) just because a different intent shares
        # a strong cue word ("note" → create_note).
        #
        # Threshold check: confidence is 1.0 for fast-path hits. If the
        # caller passes an impossible threshold (> 1.0) they explicitly
        # want every classifier short-circuited — honour that by falling
        # through so threshold semantics stay consistent across paths.
        exact_intent = self.classifier.exact_match(text)
        if exact_intent and threshold <= 1.0:
            pred = Prediction(
                intent=exact_intent,
                confidence=1.0,
                top3=[(exact_intent, 1.0)],
                raw_text=text,
                normalized_text=normalized,
            )
            self._cache_put(cache_key, pred)
            return pred

        # Deterministic arithmetic override (see _is_plain_arithmetic). Runs
        # after exact-match, before the classifiers, so basic sums land on
        # `calculate` instead of a random formula skill.
        if threshold <= 1.0 and _is_plain_arithmetic(normalized):
            pred = Prediction(
                intent="calculate",
                confidence=1.0,
                top3=[("calculate", 1.0)],
                raw_text=text,
                normalized_text=normalized,
            )
            self._cache_put(cache_key, pred)
            return pred

        # Command anchors (get_time / search_web …) — deterministic, before k-NN.
        if threshold <= 1.0:
            _anchored = _anchor_intent(normalized)
            if _anchored:
                pred = Prediction(
                    intent=_anchored,
                    confidence=1.0,
                    top3=[(_anchored, 1.0)],
                    raw_text=text,
                    normalized_text=normalized,
                )
                self._cache_put(cache_key, pred)
                return pred

        # ── Heavy tier ──────────────────────────────────────────────────
        # Every cheap tier missed, so we genuinely need embeddings. THIS is
        # where the encoder (and neural head) get loaded — on demand, once.
        #
        # ENCODER_LOCK spans the load AND the predict, deliberately. Loading
        # under the lock and then predicting outside it leaves a window where
        # try_unload_idle (which takes the same lock) can null out
        # classifier.encoder between the two — the next line then dies with
        # "'NoneType' object has no attribute 'encode'". That window was
        # harmless while nothing called try_unload_idle on a timer; the idle
        # unloader made it a live race, reproduced on the first real run.
        # ENCODER_LOCK is an RLock, so _ensure_loaded's own acquire and the
        # chat-gate encode hooks re-enter safely on this thread.
        from core.encoder_lock import ENCODER_LOCK
        with ENCODER_LOCK:
            self._ensure_loaded()

            if not self._neural_active:
                pred = self.classifier.predict(text, threshold=threshold)
                self._cache_put(cache_key, pred)
                return pred

            neural_pred = self.neural.predict(text, threshold=threshold)
            knn_pred = self.classifier.predict(text, threshold=threshold)

        if neural_pred.confidence >= _NEURAL_LOW_CONF and neural_pred.intent:
            pred = _with_merged_top3(neural_pred, knn_pred)
        else:
            # Neural unsure — k-NN drives.
            pred = _with_merged_top3(knn_pred, neural_pred)
        self._cache_put(cache_key, pred)
        return pred

    def _cache_put(self, key: tuple, pred: Prediction) -> None:
        with self._pred_cache_lock:
            self._pred_cache[key] = pred
            self._pred_cache.move_to_end(key)
            while len(self._pred_cache) > _PREDICT_CACHE_SIZE:
                self._pred_cache.popitem(last=False)

    def clear_prediction_cache(self) -> None:
        """Drop every cached prediction. Call after intents.json changes or
        a classifier rebuild so old answers don't outlive their patterns.
        """
        with self._pred_cache_lock:
            self._pred_cache.clear()


def _with_merged_top3(primary: Prediction, secondary: Prediction) -> Prediction:
    """Return ``primary`` but with ``secondary``'s leading distinct intent
    grafted into top3 (capped at 3) so the disambiguator gets both views.

    Order is preserved — secondary entries only ever fill slots not already
    occupied by primary. Probabilities aren't renormalised; the disambiguator
    only uses the *order* and the absolute top-1 / top-2 gap.
    """
    if not secondary or not secondary.top3:
        return primary
    seen = {label for label, _ in primary.top3}
    merged = list(primary.top3)
    for label, score in secondary.top3:
        if label in seen:
            continue
        merged.append((label, score))
        seen.add(label)
        if len(merged) >= 3:
            break
    return Prediction(
        intent=primary.intent,
        confidence=primary.confidence,
        top3=merged[:3],
        raw_text=primary.raw_text,
        normalized_text=primary.normalized_text,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    brain = JarvisBrain()
    for q in ["chrome kholo", "weather batao", "screenshot lo zara",
              "youtube open kro in brave browser", "open youtube website"]:
        print(brain.predict(q))
