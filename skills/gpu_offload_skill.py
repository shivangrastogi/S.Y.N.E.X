"""Voice commands for GPU offload.

Skills:
  * ``gpu_offload_on``   — persist preference + reset heavy singletons
  * ``gpu_offload_off``  — back to CPU
  * ``gpu_status``       — current pref + CUDA detection
"""
from __future__ import annotations

import logging

from core.skill_registry import skill

log = logging.getLogger(__name__)


@skill(
    name="gpu_offload_on",
    description="Switch heavy ML models (encoder / YOLO / InsightFace) to GPU "
                "on next reload — persists across restarts.",
    patterns=[
        "gpu on", "enable gpu", "gpu offload on",
        "use gpu", "switch to gpu", "use cuda",
        "enable cuda", "gpu chalu karo",
    ],
    required_entities=[],
)
def gpu_offload_on(_slots: dict) -> str:
    try:
        from core import gpu_offload as g
    except Exception as e:
        return f"gpu_offload load fail: {e}"
    info = g.detect_gpu()
    if not info["torch_installed"]:
        return ("torch nahi mila — pip install torch (CUDA build) for GPU offload.")
    if not info["torch_cuda"]:
        return ("CUDA not available on this host — preference will save but "
                "no actual speedup until a CUDA-capable PyTorch is installed.")
    changed, msg = g.set_preference(True)
    return msg


@skill(
    name="gpu_offload_off",
    description="Revert heavy ML models to CPU on next reload.",
    patterns=[
        "gpu off", "disable gpu", "gpu offload off",
        "use cpu", "switch to cpu", "back to cpu",
        "gpu band karo", "disable cuda",
    ],
    required_entities=[],
)
def gpu_offload_off(_slots: dict) -> str:
    try:
        from core import gpu_offload as g
    except Exception as e:
        return f"gpu_offload load fail: {e}"
    changed, msg = g.set_preference(False)
    return msg


@skill(
    name="gpu_status",
    description="Report GPU offload preference + CUDA availability.",
    patterns=[
        "gpu status", "cuda status", "is gpu enabled",
        "gpu hai kya", "cuda available kya hai",
        "gpu offload status", "device status",
    ],
    required_entities=[],
)
def gpu_status(_slots: dict) -> str:
    try:
        from core import gpu_offload as g
    except Exception as e:
        return f"gpu_offload load fail: {e}"
    return g.explain()
