"""Entry point for the new A.E.R.I.S JARVIS v6 PyQt5 GUI.

Mirrors ``run_gui.py``'s Windows-tuned boot order (torch imported on the main
thread BEFORE PyQt5 to dodge the WinError 1114 / DLL-init failure, single
splash, heavy ML modules pre-imported on the main thread so the BrainWorker
pays zero import cost) — but launches ``ui/aeris_v6`` instead of the old
``ui/jarvis_v31`` surface.

The older GUIs remain fully launchable via ``run_gui.py``.
"""
import os
import sys

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")


def _hf_model_cached(repo_id: str) -> bool:
    cache_root = os.environ.get("HF_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache", "huggingface", "hub")
    folder = "models--" + repo_id.replace("/", "--")
    return os.path.isdir(os.path.join(cache_root, folder))


if (_hf_model_cached("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        and not os.environ.get("HF_HUB_OFFLINE")):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

sys.setswitchinterval(0.002)

# 1. torch first (before PyQt5)
try:
    import torch  # noqa: F401
except Exception as _e:
    sys.stderr.write(f"[run_aeris_v6] WARN: torch pre-import failed: {_e}\n")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication

# single-instance guard (reuse the proven core helper)
try:
    from core.single_instance import acquire as _acquire
    _lock = _acquire("aeris.gui.v6")
    if _lock.already_running():
        sys.stderr.write("[run_aeris_v6] AERIS v6 already running — focusing.\n")
        _lock.signal_existing()
        sys.exit(0)
except Exception:
    pass

_app = QApplication.instance() or QApplication(sys.argv)

# 2. splash ASAP (reuse the old splash widget — it's self-contained)
_splash = None
try:
    from ui.jarvis_v31.splash import BootSplash
    _splash = BootSplash()
    _splash.show()
    _app.processEvents()
except Exception as _e:
    sys.stderr.write(f"[run_aeris_v6] splash unavailable: {_e}\n")

# 3. pre-import heavy ML modules on the main thread
_HEAVY = [
    ("sentence_transformers", "Loading sentence-transformers", 15),
    ("sklearn.neighbors", "Loading scikit-learn", 25),
    ("spacy", "Loading spaCy NLP runtime", 38),
    ("transformers", "Loading HuggingFace transformers", 50),
]
for _mod, _label, _pct in _HEAVY:
    if _splash is not None:
        try:
            _splash.update_status(f"{_label} ({_pct}%)")
        except Exception:
            pass
        _app.processEvents()
    try:
        __import__(_mod)
    except Exception as _e:
        sys.stderr.write(f"[run_aeris_v6] WARN: {_mod} pre-import failed: {_e}\n")
    _app.processEvents()

if _splash is not None:
    try:
        _splash.update_status("Building v6 interface (55%)")
    except Exception:
        pass
    _app.processEvents()

from ui.aeris_v6.app import launch

if __name__ == "__main__":
    sys.exit(launch(splash=_splash))
