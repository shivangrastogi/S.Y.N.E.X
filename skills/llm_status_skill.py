"""RETIRED — duplicate of ``llm_status`` in skills/llm_chat_skill.py.

Both modules registered a skill named "llm_status", producing a
"re-registered; overriding" warning on every boot and nondeterministic
ownership. The generic version in llm_chat_skill.py (backend-aware:
embedded llama.cpp OR ollama) is the survivor; this module's replies were
Ollama-only ("start: ollama serve") and misleading under the embedded
backend. File kept as a tombstone so old references don't ImportError.
"""
from __future__ import annotations

import logging

from core.skill_registry import skill  # noqa: F401  (kept for import parity)

log = logging.getLogger(__name__)


# (skill registration removed — see module docstring. The canonical
# llm_status lives in skills/llm_chat_skill.py and reports whichever
# backend is active: embedded llama.cpp or ollama.)
