"""Deterministic chain planner — multi-step requests without an LLM round-trip.

The agent loop (:mod:`core.agent_orchestrator`) can chain skills, but every
step is a local-LLM call (~7 s each on this laptop's CPU), and a 1.5B model
often picks the wrong tool. Most real multi-step requests have one of two
simple shapes, and the brain already routes each part in milliseconds:

1. **Data flow** — a command whose *result* feeds a sink::

       "weather batao aur phone pe bhejo"
       "time check karke clipboard me copy karo"
       "einstein ke baare me batao, phir isko note kar lo"
       "isko hindi me translate karo"          (sink on AERIS's LAST answer)

2. **Condition** — probe a number, compare, act (with optional else)::

       "agar battery 30 se kam hai to brightness kam karo"
       "if cpu is above 80 then task manager kholo warna time batao"

This module parses those shapes and runs them step by step: each command
step goes through the normal engine pipeline (routing, safety guards,
confirm gate all still apply), and its reply becomes the next step's input.
Anything it doesn't recognise returns ``None`` so the caller keeps its
existing path (plain segments, or the LLM agent for open-ended goals).

Pure and injectable: the engine passes ``run_command`` and the sink
callables, so tests drive the whole thing with fakes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

# ── vocabulary ──────────────────────────────────────────────────────

# Joiners that separate chain steps. "karke"/"leke" also tell us the
# producer lost its verb in the split ("weather check karke" → "weather
# check karo").
_JOINER_RE = re.compile(
    r"\s*(?:,\s*(?:(?:and\s+)?then|phir|aur\s+phir|uske\s+baad)?|;|"
    r"\b(?:and\s+then|aur\s+phir|uske\s+baad|uske\s+bad|after\s+that|then|"
    r"phir|aur|and)\b|"
    r"\b(?P<karke>kar\s*ke|karkay|karke|le\s*ke|lekar|leke)\b)\s*",
    re.IGNORECASE,
)

# Words that point back at an earlier result.
_REF_RE = re.compile(
    r"\b(?:isko|usko|ise|use|iska|uska|isse|usse|ye|yeh|wo|woh|vo|"
    r"it|this|that|result|jawab|answer|output)\b",
    re.IGNORECASE,
)

# Tokens that carry no payload of their own once the sink trigger is gone.
_FILLER = {
    "karo", "kar", "kardo", "do", "dena", "de", "dijiye", "lo", "lena",
    "le", "pe", "par", "me", "mein", "main", "mai", "ko", "ki", "ke", "ka",
    "please", "plz", "bhi", "zara", "jara", "ek", "the", "to", "a", "an",
    "into", "in", "on", "my", "mere", "mera", "meri", "sir", "bhai", "yaar",
    "aeris", "jarvis", "now", "abhi", "jaldi", "and", "aur", "then", "phir",
    "baad", "uske", "wala", "wali", "kar", "karna", "karke", "hai", "it",
}


@dataclass(frozen=True)
class Sink:
    name: str
    trigger: re.Pattern
    # Words removed before deciding whether the segment has its own payload.
    words: frozenset


def _sink(name: str, pattern: str, words: str) -> Sink:
    return Sink(name, re.compile(pattern, re.IGNORECASE),
                frozenset(words.split()))


# Order matters: first match wins ("phone pe copy bhejo" is phone).
SINKS: tuple[Sink, ...] = (
    _sink("phone",
          r"\b(?:phone|mobile)\b.*\b(?:bhej\w*|send|share)\b|"
          r"\b(?:bhej\w*|send|share)\b.*\b(?:phone|mobile)\b",
          "phone mobile bhejo bhej bhejdo bhejna send share"),
    _sink("clipboard",
          r"\b(?:copy|clipboard)\b",
          "copy clipboard kar karo"),
    _sink("file",
          r"\bfile\b.*\b(?:save|likh\w*|daal\w*|store)\b|"
          r"\b(?:save|write)\b.*\bfile\b",
          "file save likho likh likhdo daalo daal store write"),
    _sink("note",
          r"\bnote\w*\b|\blikh\s*(?:lo|do|dena)\b|\blikho\b|"
          r"\bsave\s*(?:kar|karo|kar\s*lo|it|this)\b|\bsave\b$",
          "note notes notepad likh likho save kar lo do dena"),
    _sink("translate",
          r"\btranslate\b|\banuvaad\b|\banuvad\b",
          "translate anuvaad anuvad"),
    _sink("summarize",
          r"\bsummar\w*\b|\bsaar\b|\btl;?dr\b|\bshort\s*(?:me|mein|kar\w*)\b|"
          r"\bchhota\s*kar\w*\b",
          "summarize summarise summary saar tldr short chhota karo kar"),
)

_LANGS = {
    "hindi": "hindi", "english": "english", "angrezi": "english",
    "french": "french", "spanish": "spanish", "german": "german",
    "japanese": "japanese", "chinese": "chinese", "arabic": "arabic",
    "bengali": "bengali", "bangla": "bengali", "marathi": "marathi",
    "tamil": "tamil", "telugu": "telugu", "gujarati": "gujarati",
    "punjabi": "punjabi", "urdu": "urdu", "russian": "russian",
    "italian": "italian", "korean": "korean", "portuguese": "portuguese",
}

# Condition grammar.
_IF_RE = re.compile(
    r"^\s*(?:agar|if|jab|when)\s+(?P<cond>.+?)\s*(?:,\s*)?"
    r"\b(?:to|toh|tab|then)\b\s*(?P<then>.+?)"
    r"(?:\s*,?\s*\b(?:warna|varna|nahi\s*to|nahin\s*to|otherwise|else)\b\s*"
    r"(?P<else>.+))?\s*$",
    re.IGNORECASE,
)
_LT = (r"se\s+kam|se\s+neeche|se\s+niche|below|less\s+than|under|"
       r"lower\s+than|kam\s+hai|<")
_GT = (r"se\s+(?:zyada|jyada|zada|jada|upar|oopar)|above|more\s+than|over|"
       r"greater\s+than|higher\s+than|zyada\s+hai|>")
_NUM = r"(?P<num>\d+(?:\.\d+)?)\s*(?:%|percent|pratishat|degree\w*)?"
_CMP_RE = re.compile(
    rf"(?:{_NUM}\s*(?P<op1>{_LT}|{_GT}))|(?:(?P<op2>{_LT}|{_GT})\s*{_NUM.replace('num', 'num2')})",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(%)?")

# Condition subject → a phrasing that is a verbatim skill pattern, so the
# probe routes by exact match instead of a guess.
_PROBES = {
    "battery": "battery status", "charge": "battery status",
    "cpu": "cpu usage", "processor": "cpu usage",
    "ram": "ram usage", "memory": "ram usage",
    "disk": "disk space", "storage": "disk space",
    "weather": "weather batao", "mausam": "weather batao",
    "temperature": "weather batao", "tapman": "weather batao",
}
_READING_WORD = {
    "charge": "battery", "processor": "cpu", "memory": "ram",
    "storage": "disk", "mausam": "", "temperature": "", "tapman": "",
    "weather": "",
}

# A command reply that means the step did not do its job.
_FAIL_RE = re.compile(
    r"^(?:error\b|tool '|ye kaam karna seekh raha|samajh nahi|"
    r"ye samajh nahi|poora nahi kar)", re.IGNORECASE)


# ── plan model ──────────────────────────────────────────────────────

@dataclass
class Step:
    kind: str                     # "command" | "sink"
    text: str
    sink: Optional[str] = None
    args: dict = field(default_factory=dict)


@dataclass
class Condition:
    probe: str                    # command that yields the number
    op: str                       # "lt" | "gt"
    value: float
    subject: str                  # word used to find the number in the reply
    label: str = ""               # what the user called it, for the verdict


@dataclass
class Plan:
    steps: list[Step] = field(default_factory=list)
    condition: Optional[Condition] = None
    then_text: str = ""
    else_text: str = ""
    uses_previous_reply: bool = False   # first sink consumes AERIS's last answer

    @property
    def kind(self) -> str:
        return "condition" if self.condition else "flow"


@dataclass
class TraceItem:
    step: Step
    output: str
    ok: bool = True


@dataclass
class ChainResult:
    reply: str
    trace: list[TraceItem] = field(default_factory=list)
    stopped: str = "done"         # done | failed | paused | skipped


# ── parsing ─────────────────────────────────────────────────────────

def _payload_words(seg: str, sink: Sink) -> list[str]:
    toks = re.findall(r"[\w%]+", seg.lower())
    return [t for t in toks
            if t not in sink.words and t not in _FILLER and t not in _LANGS
            and not _REF_RE.fullmatch(t)]


def match_sink(seg: str) -> Optional[Sink]:
    for s in SINKS:
        if s.trigger.search(seg):
            return s
    return None


def _consumer(seg: str) -> Optional[Step]:
    """A sink segment that takes its payload from the previous step.

    It must either point back ("isko", "ye", "it") or carry no payload of
    its own — "note karo ki doodh lana hai" has one, so it is a plain
    command, not a consumer."""
    sink = match_sink(seg)
    if sink is None:
        return None
    if not (_REF_RE.search(seg) or not _payload_words(seg, sink)):
        return None
    # A pointer plus several words of its own ("ye line copy karo: hello
    # world") is the user dictating content, not chaining.
    if len(_payload_words(seg, sink)) > 2:
        return None
    args: dict = {}
    if sink.name == "translate":
        args["lang"] = _lang_in(seg) or "english"
    return Step(kind="sink", text=seg, sink=sink.name, args=args)


def _lang_in(seg: str) -> Optional[str]:
    for tok in re.findall(r"[a-z]+", seg.lower()):
        if tok in _LANGS:
            return _LANGS[tok]
    return None


# Answer-producing verbs the command splitter's list doesn't need but a
# chain producer usually ends in ("joke sunao", "hello bolo").
_EXTRA_VERBS = frozenset({
    "sunao", "suna", "bolo", "bol", "samjhao", "check", "dekho", "nikalo",
    "padho", "get", "give", "tell", "say", "explain", "summarize", "summarise",
    "translate", "copy", "send", "bhejo", "likho", "banao", "bana",
})


def _has_verb(piece: str) -> bool:
    from core.utterance_parser import _VERB_HINTS
    return any(t in _VERB_HINTS or t in _EXTRA_VERBS
               for t in re.findall(r"\w+", piece.lower()))


def _split(text: str) -> list[tuple[str, bool]]:
    """Split on joiners; the bool says the piece ended at a karke/leke
    joiner (so it lost its verb).

    A verb-less piece is part of the next one, not a step of its own:
    "einstein aur newton ke baare me batao" is one request. It is glued
    back using the ORIGINAL text between them, so nothing is reworded."""
    spans: list[tuple[int, int, bool]] = []
    pos = 0
    for m in _JOINER_RE.finditer(text):
        if text[pos:m.start()].strip(" ,;"):
            spans.append((pos, m.start(), bool(m.group("karke"))))
        pos = m.end()
    if text[pos:].strip(" ,;.?!"):
        spans.append((pos, len(text), False))

    merged: list[tuple[int, int, bool]] = []
    carry_start: Optional[int] = None
    for start, end, lost in spans:
        s = start if carry_start is None else carry_start
        piece = text[start:end]
        is_last = (start, end, lost) == spans[-1]
        if not lost and not is_last and not _has_verb(piece) \
                and match_sink(piece) is None:
            carry_start = s
            continue
        merged.append((s, end, lost))
        carry_start = None
    return [(text[s:e].strip(" ,;.?!"), lost) for s, e, lost in merged]


def _restore_verb(piece: str, lost: bool) -> str:
    if not lost:
        return piece
    low = piece.lower()
    if re.search(r"\b(?:screenshot|photo|pic|picture|selfie)\b", low):
        return f"{piece} lo"
    return f"{piece} karo"


def plan(text: str, *, has_previous_reply: bool = False) -> Optional[Plan]:
    """Parse ``text`` into a chain plan, or ``None`` if it isn't one."""
    if not text or not text.strip():
        return None
    text = text.strip()

    cond = _plan_condition(text)
    if cond is not None:
        return cond

    pieces = _split(text)
    if len(pieces) == 1:
        # Single consumer pointing at AERIS's previous answer:
        # "isko note kar lo", "ye hindi me translate karo". Needs an
        # explicit pointer — a bare "copy karo" is the clipboard skill's
        # own slot prompt, not a chain. Phone is left to its skills
        # ("yeh phone pe bhejo" already means "send the clipboard").
        if not has_previous_reply or not _REF_RE.search(text):
            return None
        step = _consumer(text)
        if step is None or step.sink == "phone":
            return None
        return Plan(steps=[step], uses_previous_reply=True)

    steps: list[Step] = []
    for i, (piece, lost) in enumerate(pieces):
        step = _consumer(piece) if i > 0 else None
        if step is None:
            steps.append(Step(kind="command", text=_restore_verb(piece, lost)))
        else:
            steps.append(step)
    # Only a chain if data actually flows: some sink consumes an earlier
    # command. "chrome aur notepad kholo" stays on the normal splitter.
    if not any(s.kind == "sink" for s in steps):
        return None
    if steps[0].kind != "command":
        return None
    return Plan(steps=steps)


def _plan_condition(text: str) -> Optional[Plan]:
    m = _IF_RE.match(text)
    if not m:
        return None
    cond_text = m.group("cond").strip()
    cm = _CMP_RE.search(cond_text)
    if not cm:
        return None                     # not numeric — leave it to the agent
    num = cm.group("num") or cm.group("num2")
    op_word = (cm.group("op1") or cm.group("op2") or "").lower()
    op = "lt" if re.fullmatch(_LT, op_word, re.IGNORECASE) else "gt"
    subject_text = (cond_text[:cm.start()] + " " + cond_text[cm.end():])
    subject_text = re.sub(r"\b(?:is|hai|ho|h|ka|ki|ke|level|the|my|mera|"
                          r"meri|agar|if)\b", " ", subject_text,
                          flags=re.IGNORECASE)
    subject_text = re.sub(r"\s+", " ", subject_text).strip(" ,%")
    if not subject_text:
        return None
    subject = subject_text.split()[0].lower()
    then_text = m.group("then").strip(" ,.")
    else_text = (m.group("else") or "").strip(" ,.")
    if not then_text:
        return None
    probe = _PROBES.get(subject, subject_text)
    label = subject
    # The reply names the reading in English ("CPU: 23%", "Battery 45%").
    subject = _READING_WORD.get(subject, subject)
    return Plan(
        condition=Condition(probe=probe, op=op, value=float(num),
                            subject=subject, label=label),
        then_text=then_text, else_text=else_text)


# ── execution ───────────────────────────────────────────────────────

# run_command(text) -> (reply, intent, paused)
#   paused=True when the step asked the user something (slot / disambig /
#   confirm) — the chain must stop and let the user answer.
RunCommand = Callable[[str], tuple[Optional[str], Optional[str], bool]]
SinkFn = Callable[[str, dict], str]


def extract_number(reply: str, subject: str) -> Optional[float]:
    """The number in ``reply`` that belongs to ``subject``.

    Nearest number after the subject word wins ("CPU 23%, RAM 61%" with
    subject "ram" → 61); else the first percentage; else the first number."""
    if not reply:
        return None
    low = reply.lower()
    idx = low.find(subject.lower()) if subject else -1
    if idx >= 0:
        # "RAM: 7.2 GB / 15.4 GB (61%)" — the percentage near the subject
        # is the reading, not the first raw number.
        window = low[idx: idx + 60]
        for m in _NUMBER_RE.finditer(window):
            if m.group(2):
                return float(m.group(1))
        m = _NUMBER_RE.search(low, idx)
        if m:
            return float(m.group(1))
    for m in _NUMBER_RE.finditer(low):
        if m.group(2):
            return float(m.group(1))
    m = _NUMBER_RE.search(low)
    return float(m.group(1)) if m else None


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def _failed(reply: Optional[str]) -> bool:
    return not reply or not reply.strip() or bool(_FAIL_RE.match(reply.strip()))


class ChainRunner:
    """Executes a :class:`Plan`. Create per engine; stateless across runs."""

    def __init__(self, run_command: RunCommand, sinks: dict[str, SinkFn],
                 *, optimize: Optional[Callable[[str, str], Optional[str]]] = None,
                 max_steps: int = 6):
        self.run_command = run_command
        self.sinks = sinks
        # optimize(producer_intent, sink_name) -> fused intent to run
        # instead (screenshot → phone becomes screenshot_to_phone).
        self.optimize = optimize
        self.max_steps = max_steps

    def run(self, p: Plan, *, previous_reply: str = "") -> ChainResult:
        if p.condition is not None:
            return self._run_condition(p)
        return self._run_flow(p.steps, previous_reply if p.uses_previous_reply
                              else "")

    # -- data flow ---------------------------------------------------

    def _run_flow(self, steps: list[Step], carry: str) -> ChainResult:
        trace: list[TraceItem] = []
        replies: list[str] = []
        last_intent: Optional[str] = None
        for n, step in enumerate(steps[: self.max_steps], start=1):
            if step.kind == "command":
                reply, intent, paused = self.run_command(step.text)
                if paused:
                    trace.append(TraceItem(step, reply or "", ok=True))
                    replies.append(reply or "")
                    return ChainResult("\n".join(r for r in replies if r),
                                       trace, "paused")
                if _failed(reply):
                    trace.append(TraceItem(step, reply or "", ok=False))
                    replies.append(self._fail_msg(n, step, reply))
                    return ChainResult("\n".join(r for r in replies if r),
                                       trace, "failed")
                trace.append(TraceItem(step, reply))
                replies.append(reply)
                carry, last_intent = reply, intent
                continue

            # sink step
            fused = (self.optimize(last_intent or "", step.sink or "")
                     if self.optimize and last_intent else None)
            if fused:
                reply, _intent, paused = self.run_command(fused)
                out = reply or ""
                ok = not _failed(out)
                trace.append(TraceItem(step, out, ok=ok))
                replies.append(out)
                if not ok or paused:
                    return ChainResult("\n".join(r for r in replies if r),
                                       trace, "paused" if paused else "failed")
                continue
            payload = _clean_payload(carry)
            if not payload:
                trace.append(TraceItem(step, "", ok=False))
                replies.append(f"Step {n}: {_SINK_LABEL.get(step.sink, step.sink)}"
                               f" ke liye pichle step se kuch mila hi nahi.")
                return ChainResult("\n".join(r for r in replies if r),
                                   trace, "failed")
            fn = self.sinks.get(step.sink or "")
            try:
                out = fn(payload, dict(step.args)) if fn else \
                    f"'{step.sink}' abhi nahi kar sakta."
            except Exception as e:  # a sink blowing up must not kill the turn
                out = f"Error: {step.sink} fail hua: {e}"
            ok = not _failed(out)
            trace.append(TraceItem(step, out, ok=ok))
            replies.append(out)
            if not ok:
                return ChainResult("\n".join(r for r in replies if r),
                                   trace, "failed")
            # Transforming sinks hand their output on ("translate karke
            # note karo" saves the translation, not the original).
            if step.sink in ("translate", "summarize"):
                carry = _strip_backend_tag(out)
        return ChainResult("\n".join(r for r in replies if r), trace, "done")

    @staticmethod
    def _fail_msg(n: int, step: Step, reply: Optional[str]) -> str:
        why = (reply or "").strip() or "koi jawab nahi aaya"
        return (f"Step {n} ('{step.text}') nahi hua: {why} "
                f"Isliye aage ke steps roke.")

    # -- condition ---------------------------------------------------

    def _run_condition(self, p: Plan) -> ChainResult:
        c = p.condition
        assert c is not None
        probe_step = Step(kind="command", text=c.probe)
        reply, _intent, paused = self.run_command(c.probe)
        trace = [TraceItem(probe_step, reply or "", ok=not _failed(reply))]
        if paused or _failed(reply):
            return ChainResult(
                f"'{c.probe}' check nahi kar paaya, isliye condition "
                f"decide nahi hui. ({(reply or '').strip()})".strip(),
                trace, "failed")
        got = extract_number(reply or "", c.subject)
        if got is None:
            return ChainResult(
                f"'{c.probe}' ke jawab mein number nahi mila: {reply}",
                trace, "failed")
        holds = got < c.value if c.op == "lt" else got > c.value
        rel = "kam" if c.op == "lt" else "zyada"
        name = c.label or c.subject
        name = name.upper() if len(name) <= 3 else name.capitalize()
        verdict = (f"{name} {_fmt(got)} hai — "
                   f"{_fmt(c.value)} se {rel} "
                   f"{'hai' if holds else 'nahi hai'}.")
        branch = p.then_text if holds else p.else_text
        if not branch:
            return ChainResult(f"{verdict} Isliye kuch nahi kiya.",
                               trace, "skipped")
        sub = plan(branch)
        if sub is not None and sub.condition is None:
            res = self._run_flow(sub.steps, "")
        else:
            r, _i, paused = self.run_command(branch)
            st = Step(kind="command", text=branch)
            ok = not _failed(r)
            res = ChainResult(r or "", [TraceItem(st, r or "", ok=ok)],
                              "paused" if paused else
                              ("done" if ok else "failed"))
        return ChainResult(f"{verdict}\n{res.reply}".strip(),
                           trace + res.trace, res.stopped)


_SINK_LABEL = {
    "phone": "phone pe bhejne", "clipboard": "copy karne",
    "file": "file me save karne", "note": "note karne",
    "translate": "translate karne", "summarize": "summary banane",
}

_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿️]")


def _strip_backend_tag(text: str) -> str:
    return re.sub(r"^\[\w+\]\s*", "", text or "").strip()


def _clean_payload(text: str) -> str:
    return _EMOJI_RE.sub("", text or "").strip()


# ── default sink helpers (used by the engine) ───────────────────────

def summarize_text(text: str, generate: Optional[Callable[[str], Optional[str]]]
                   = None, max_sentences: int = 2) -> str:
    """LLM summary when a model is available, else the leading sentences.

    The extractive fallback keeps the chain working offline and fast."""
    if generate is not None:
        try:
            out = generate(text)
        except Exception:
            out = None
        if out and out.strip():
            return out.strip()
    parts = re.split(r"(?<=[.!?।])\s+", text.strip())
    short = " ".join(parts[:max_sentences]).strip()
    if len(short) > 280:
        short = short[:277].rstrip() + "..."
    return short
