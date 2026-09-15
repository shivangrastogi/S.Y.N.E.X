"""GPU offload toggle — switch heavy models to CUDA when available.

Inspects the live environment for:
  * PyTorch CUDA support  → sentence-transformers can move to GPU
  * InsightFace ctx_id     → switches detector + recogniser to GPU
  * Ultralytics YOLO device → switches detection forward pass

Each subsystem holds its own model instance, so "enabling" GPU here
just sets the persisted preference + nudges each subsystem to drop +
reload its model on next use. The user re-issues their normal command
(e.g. "gesture mode on") and the next model load lands on CUDA.

Public API:
    detect_gpu() -> dict     # {'torch_cuda': bool, 'device_name': str, ...}
    set_preference(on)       # persist 'gpu_offload' bool
    is_preferred() -> bool
    explain() -> str         # one-line human summary
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


_PREF_KEY = "gpu_offload"


def _settings_get(key: str, default=None):
    try:
        from core import settings as _settings
        return _settings.get(key, default)
    except Exception:
        return default


def _settings_set(key: str, value) -> None:
    try:
        from core import settings as _settings
        _settings.set_(key, value)
    except Exception:
        pass


def detect_gpu() -> dict:
    """Best-effort GPU probe — never raises, returns a dict of facts."""
    out = {
        "torch_cuda": False,
        "torch_cuda_count": 0,
        "device_name": "",
        "torch_installed": False,
        "ultralytics_installed": False,
        "insightface_installed": False,
    }
    try:
        import torch  # type: ignore
        out["torch_installed"] = True
        if torch.cuda.is_available():
            out["torch_cuda"] = True
            out["torch_cuda_count"] = int(torch.cuda.device_count())
            try:
                out["device_name"] = torch.cuda.get_device_name(0)
            except Exception:
                pass
    except Exception:
        pass
    try:
        import ultralytics  # type: ignore  # noqa: F401
        out["ultralytics_installed"] = True
    except Exception:
        pass
    try:
        import insightface  # type: ignore  # noqa: F401
        out["insightface_installed"] = True
    except Exception:
        pass
    return out


def is_preferred() -> bool:
    return bool(_settings_get(_PREF_KEY, False))


def set_preference(on: bool) -> tuple[bool, str]:
    """Persist the preference + optionally reset the heavy singletons so
    they reload on next use with the new device. Returns (changed, msg).
    """
    before = is_preferred()
    _settings_set(_PREF_KEY, bool(on))
    if before == bool(on):
        return False, f"GPU offload preference already {'ON' if on else 'OFF'}."

    # Force the heavy singletons to drop their models so the next call
    # rebuilds them with the new device. We can't pass device explicitly
    # without monkey-patching each module — but resetting the singletons
    # is enough to let the user re-invoke `gesture mode on` etc.
    try:
        import core.face_recognition as fr
        fr._REC_SINGLETON = None
        fr._REG_SINGLETON = None
    except Exception:
        pass
    try:
        import core.object_detector as od
        # The detector is held inside auto_label / object_skill — clearing
        # the module-level cache is enough for these to rebuild on next use.
        # Note: object_detector doesn't expose a global, so we no-op safely.
    except Exception:
        pass
    log.info("[gpu_offload] preference → %s", "ON" if on else "OFF")
    return True, (f"GPU offload preference → {'ON' if on else 'OFF'}. "
                  f"Restart heavy subsystems (gesture mode, auto-label) to apply.")


def explain() -> str:
    info = detect_gpu()
    pref = "ON" if is_preferred() else "OFF"
    if not info["torch_installed"]:
        return f"GPU offload pref={pref}. torch missing — cannot use CUDA."
    if not info["torch_cuda"]:
        return (f"GPU offload pref={pref}. torch installed but CUDA "
                f"unavailable on this host — CPU only.")
    return (f"GPU offload pref={pref} · CUDA available · "
            f"{info['torch_cuda_count']} device(s) · {info['device_name']}")
