"""Embedded local LLM — conversation without Ollama, without any server.

Runs a small quantized instruct model (default: Qwen2.5-1.5B-Instruct
Q4_K_M, ~1 GB) directly inside the AERIS process via ``llama-cpp-python``.
Chosen over the Ollama path because:

  * zero setup — no separate server to install, start, or keep running;
  * fully offline and private, matching the local-first principle;
  * CPU-only friendly — built for laptops with no dGPU. Threads are
    capped and the context window kept small so RAM stays ~1.5 GB.

Lifecycle mirrors the brain's idle policy:
  * **Lazy load** — the model file is memory-mapped only on the FIRST
    chat request (first reply pays ~2-6 s of load; the window never
    blocks because callers run on worker threads).
  * **Idle unload** — ``maybe_unload_idle()`` drops the weights after
    ``_IDLE_UNLOAD_S`` without a request, so casual skill-only usage
    costs zero RAM.

Interface is deliberately tiny: ``available()``, ``chat(messages) ->
str | None``. ``core/llm_chat.py`` consumes it as the "embedded"
backend when ``settings.llm_backend == "embedded"``.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MODEL_DIR = os.path.join(_ROOT, "data", "models", "llm")

# First *.gguf in data/models/llm/ wins; this name is the shipped default.
_DEFAULT_MODEL = "qwen2.5-1.5b-instruct-q4_k_m.gguf"

_CTX_TOKENS = 2048          # context window — small keeps RAM + prefill sane
_MAX_REPLY_TOKENS = 120     # replies are TTS-spoken — 2 short sentences max
_IDLE_UNLOAD_S = 5 * 60.0


def idle_unload_seconds() -> float:
    """Idle window before the gguf is released, read at call time.

    Resolution order:
      1. ``AERIS_LLM_IDLE_UNLOAD_S`` — the LLM alone (it is the most expensive
         thing here to reload, so you may want to hold it longer than the
         encoder).
      2. ``AERIS_IDLE_UNLOAD_S`` — the process-wide window, so one setting
         governs every unloadable resource.
      3. the 5-minute default.

    This used to be a bare module constant, which meant `AERIS_IDLE_UNLOAD_S`
    governed the encoder and spaCy but silently *not* the LLM — and the LLM is
    the biggest single chunk in the process (~1 GB). Setting the window to a
    minute gave back ~500 MB in a minute and the other gigabyte five minutes
    later, with nothing explaining why. ``0`` disables unloading.
    """
    for var in ("AERIS_LLM_IDLE_UNLOAD_S", "AERIS_IDLE_UNLOAD_S"):
        raw = os.environ.get(var)
        if raw is None or not str(raw).strip():
            continue
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            log.warning("[local_llm] bad %s=%r — ignoring", var, raw)
    return _IDLE_UNLOAD_S


def _model_path() -> Optional[str]:
    p = os.path.join(_MODEL_DIR, _DEFAULT_MODEL)
    if os.path.isfile(p):
        return p
    try:
        for f in sorted(os.listdir(_MODEL_DIR)):
            if f.lower().endswith(".gguf"):
                return os.path.join(_MODEL_DIR, f)
    except OSError:
        pass
    return None


class LocalLLM:
    """Thread-safe lazy wrapper around one llama.cpp model instance."""

    def __init__(self):
        self._lock = threading.Lock()
        self._llm = None
        self._last_used = 0.0
        self._load_failed = False

    # ── availability ─────────────────────────────────────────────────
    def available(self) -> bool:
        """True when a model file exists and llama-cpp is importable.
        Cheap — does NOT load the model."""
        if self._load_failed:
            return False
        if _model_path() is None:
            return False
        try:
            import llama_cpp  # noqa: F401
            return True
        except Exception:
            return False

    def status(self) -> dict:
        path = _model_path()
        return {
            "backend": "embedded",
            "model_file": os.path.basename(path) if path else None,
            "loaded": self._llm is not None,
            "load_failed": self._load_failed,
        }

    # ── lifecycle ────────────────────────────────────────────────────
    def _ensure_loaded(self):
        with self._lock:
            if self._llm is not None:
                return self._llm
            path = _model_path()
            if path is None:
                return None
            try:
                from llama_cpp import Llama
                t0 = time.perf_counter()
                # n_threads: half the cores, min 2 — same "be gentle on
                # weak laptops" policy as the OMP caps in run_gui.py.
                n_threads = max(2, (os.cpu_count() or 4) // 2)
                self._llm = Llama(
                    model_path=path,
                    n_ctx=_CTX_TOKENS,
                    n_threads=n_threads,
                    n_gpu_layers=0,      # CPU-only by design
                    verbose=False,
                )
                log.info("[local_llm] loaded %s in %.1fs (threads=%d)",
                         os.path.basename(path),
                         time.perf_counter() - t0, n_threads)
            except Exception as e:
                log.warning("[local_llm] load failed: %s", e)
                self._load_failed = True
                self._llm = None
            return self._llm

    def maybe_unload_idle(self) -> bool:
        """Drop weights after idle window. Safe from any thread."""
        with self._lock:
            if self._llm is None:
                return False
            window = idle_unload_seconds()
            if window <= 0:
                return False        # 0 = never unload (matches the brain)
            if time.monotonic() - self._last_used < window:
                return False
            log.info("[local_llm] idle — unloading model")
            self._llm = None
            import gc
            gc.collect()
            return True

    # ── inference ────────────────────────────────────────────────────
    def chat(self, messages: list[dict],
             max_tokens: int = _MAX_REPLY_TOKENS) -> Optional[str]:
        """OpenAI-style messages → reply text, or None on any failure.
        Serialized by the lock — llama.cpp contexts are not re-entrant.
        """
        llm = self._ensure_loaded()
        if llm is None:
            return None

        # Anti-echo reference: small models under quantization sometimes
        # lock onto their own previous reply and repeat it verbatim for
        # every new input (observed with Qwen 1.5B Q4). We compare fresh
        # output against the last assistant turn and re-roll once hotter.
        prev_reply = ""
        for m in reversed(messages):
            if m.get("role") == "assistant":
                prev_reply = (m.get("content") or "").strip().lower()
                break

        with self._lock:
            self._last_used = time.monotonic()
            for attempt, (temp, rp) in enumerate(((0.7, 1.25), (1.0, 1.5))):
                try:
                    out = llm.create_chat_completion(
                        messages=messages,
                        max_tokens=max_tokens,
                        temperature=temp,
                        top_p=0.9,
                        repeat_penalty=rp,
                    )
                    text = (out["choices"][0]["message"]["content"] or "").strip()
                except Exception as e:
                    log.warning("[local_llm] chat failed: %s", e)
                    return None
                self._last_used = time.monotonic()
                if not text:
                    return None
                if prev_reply and text.strip().lower() == prev_reply:
                    log.info("[local_llm] echoed previous reply — re-roll "
                             "(attempt %d)", attempt + 1)
                    continue
                return text
            return None    # echoed twice — better silent than a broken loop

    def generate(self, prompt: str, system: str = "",
                 max_tokens: int = 400,
                 temperature: float = 0.3) -> Optional[str]:
        """Single-shot LONG-FORM generation with a CLEAN prompt.

        Unlike the assistant ``chat()`` path this carries no persona, no
        Hinglish style rules, and no 120-token TTS cap — it exists for
        working text: translations, summaries, rewrites, doc answers.
        Standalone by construction (in-process llama.cpp, no network).
        """
        if not (prompt or "").strip():
            return None
        llm = self._ensure_loaded()
        if llm is None:
            return None
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        with self._lock:
            self._last_used = time.monotonic()
            try:
                out = llm.create_chat_completion(
                    messages=messages,
                    max_tokens=max(32, min(512, int(max_tokens))),
                    temperature=temperature,
                    top_p=0.9,
                    repeat_penalty=1.15,
                )
                text = (out["choices"][0]["message"]["content"] or "").strip()
                self._last_used = time.monotonic()
                return text or None
            except Exception as e:
                log.warning("[local_llm] generate failed: %s", e)
                return None

    def chat_json(self, messages: list[dict],
                  max_tokens: int = 160) -> Optional[str]:
        """Like ``chat`` but constrained to emit ONE valid JSON object.

        Uses llama.cpp's grammar-backed ``response_format={"type":
        "json_object"}`` — the sampler literally cannot produce non-JSON,
        which is what makes a 1.5B model reliable enough for tool calls.
        Falls back to an unconstrained low-temperature call on old
        llama-cpp builds without response_format support; the caller's
        JSON extractor handles that path's noise.
        """
        llm = self._ensure_loaded()
        if llm is None:
            return None
        with self._lock:
            self._last_used = time.monotonic()
            base = dict(messages=messages, max_tokens=max_tokens,
                        temperature=0.1, top_p=0.9, repeat_penalty=1.1)
            for kwargs in (dict(base, response_format={"type": "json_object"}),
                           base):
                try:
                    out = llm.create_chat_completion(**kwargs)
                    text = (out["choices"][0]["message"]["content"] or "").strip()
                    self._last_used = time.monotonic()
                    return text or None
                except TypeError:
                    # response_format unsupported → retry unconstrained.
                    continue
                except Exception as e:
                    log.warning("[local_llm] chat_json failed: %s", e)
                    return None
            return None


_INSTANCE: Optional[LocalLLM] = None
_INSTANCE_LOCK = threading.Lock()


def get() -> LocalLLM:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = LocalLLM()
        return _INSTANCE


def peek() -> Optional[LocalLLM]:
    """The existing instance, or None — never constructs one.

    For callers that only want to ask "is there an LLM to clean up?", such as
    the idle-unload sweep. `get()` would materialise a LocalLLM on a machine
    that has never used the LLM, which is exactly the kind of
    construct-to-inspect that has bitten this codebase before.
    """
    with _INSTANCE_LOCK:
        return _INSTANCE
