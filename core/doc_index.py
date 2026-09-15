"""Document QA index — embeds a folder's text + asks natural-language questions.

Walks a folder, reads supported text files (``.txt``, ``.md``, ``.py``,
``.json``, ``.log``, ``.csv``, ``.rst``), splits each into ~800-character
chunks, encodes each chunk via the live sentence-transformer encoder, and
stores everything in a per-index pickle. Queries embed the question and
return top-K chunks by cosine similarity.

Designed to be cheap when the brain's encoder is already loaded — we
re-use ``IntentClassifier._ensure_encoder`` so we don't double-load the
~120 MB model.

Public API:
    idx = get_doc_index()
    idx.build(folder)              # walk + chunk + embed + persist
    idx.query(q, top_k=5) -> list[dict]
    idx.stats() -> dict
    idx.clear() -> int
"""
from __future__ import annotations

import json
import logging
import math
import os
import pickle
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_INDEX_PATH = _ROOT / "data" / "doc_index.pkl"
_META_PATH = _ROOT / "data" / "doc_index_meta.json"

_SUPPORTED_EXT = {".txt", ".md", ".py", ".json", ".log", ".csv", ".rst",
                  ".yaml", ".yml", ".pdf", ".docx"}
_BINARY_EXT = {".pdf", ".docx"}
_MAX_BINARY_BYTES = 8 * 1024 * 1024   # pdf/docx are container formats
_MAX_PDF_PAGES = 80
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
              "target", "dist", "build", "out", ".idea", ".vscode"}
_MAX_FILES = 800
_MAX_FILE_BYTES = 256 * 1024     # 256 KB per file cap
_CHUNK_CHARS = 800
_CHUNK_OVERLAP = 80


_NP_OK = True
try:
    import numpy as _np  # type: ignore
except Exception:
    _np = None
    _NP_OK = False


def _read_text(path: Path) -> Optional[str]:
    """Extract plain text from any supported file — all local parsers,
    nothing leaves the machine. PDF via pypdf, DOCX via python-docx,
    everything else read as UTF-8 text."""
    suffix = path.suffix.lower()
    try:
        cap = _MAX_BINARY_BYTES if suffix in _BINARY_EXT else _MAX_FILE_BYTES
        if path.stat().st_size > cap:
            return None
        if suffix == ".pdf":
            return _read_pdf(path)
        if suffix == ".docx":
            return _read_docx(path)
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _read_pdf(path: Path) -> Optional[str]:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages[:_MAX_PDF_PAGES]:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(pages).strip()
        return text or None
    except Exception as e:
        log.debug("[doc_index] pdf read failed %s: %s", path.name, e)
        return None


def _read_docx(path: Path) -> Optional[str]:
    try:
        import docx
        d = docx.Document(str(path))
        parts = [p.text for p in d.paragraphs if p.text.strip()]
        for table in d.tables:
            for row in table.rows:
                parts.append("  ".join(c.text for c in row.cells))
        text = "\n".join(parts).strip()
        return text or None
    except Exception as e:
        log.debug("[doc_index] docx read failed %s: %s", path.name, e)
        return None


def _chunk(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    out: list[str] = []
    n = len(text)
    step = max(1, _CHUNK_CHARS - _CHUNK_OVERLAP)
    for i in range(0, n, step):
        piece = text[i:i + _CHUNK_CHARS].strip()
        if len(piece) >= 60:    # skip tiny fragments
            out.append(piece)
    return out


def _walk(folder: Path) -> list[Path]:
    files: list[Path] = []
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in names:
            p = Path(root) / name
            if p.suffix.lower() in _SUPPORTED_EXT:
                files.append(p)
                if len(files) >= _MAX_FILES:
                    return files
    return files


def _get_encoder():
    """Get a sentence-transformer encoder, reusing the brain's instance
    if already loaded — avoids paying the ~120 MB load twice."""
    try:
        from core.brain import JarvisBrain
    except Exception:
        JarvisBrain = None
    try:
        from core.intent_classifier import IntentClassifier, ENCODER_NAME
    except Exception:
        return None
    # The classifier's lazy-load helper.
    try:
        ic = IntentClassifier(
            intents_path=str(_ROOT / "data" / "intents.json"),
            models_dir=str(_ROOT / "data" / "models"),
            lazy=True,
        )
        ic._ensure_encoder()
        return ic.encoder
    except Exception as e:
        log.info("[doc_index] encoder fetch failed: %s", e)
        return None


class DocIndex:
    def __init__(self):
        self._lock = threading.RLock()
        self._embeddings = None         # np.ndarray (N, D)
        self._meta: list[dict] = []     # parallel to embeddings rows
        self._folder: str = ""
        self._loaded = False

    # ── load/save ────────────────────────────────────────────────

    def _try_load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not _INDEX_PATH.exists() or not _NP_OK:
            return
        try:
            with open(_INDEX_PATH, "rb") as f:
                blob = pickle.load(f)
            self._embeddings = _np.asarray(blob["embeddings"], dtype=_np.float32)
            self._meta = list(blob.get("meta") or [])
            self._folder = str(blob.get("folder") or "")
            log.info("[doc_index] loaded %d chunks from %s",
                     len(self._meta), _INDEX_PATH)
        except Exception as e:
            log.info("[doc_index] load failed: %s", e)

    def _save(self) -> None:
        try:
            _INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_INDEX_PATH, "wb") as f:
                pickle.dump({
                    "embeddings": self._embeddings.tolist() if self._embeddings is not None else [],
                    "meta": self._meta,
                    "folder": self._folder,
                }, f)
            with open(_META_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "folder": self._folder,
                    "chunks": len(self._meta),
                    "files": len({m["file"] for m in self._meta}) if self._meta else 0,
                }, f, indent=2)
        except Exception as e:
            log.warning("[doc_index] save failed: %s", e)

    # ── public ───────────────────────────────────────────────────

    def stats(self) -> dict:
        self._try_load()
        with self._lock:
            return {
                "folder": self._folder,
                "chunks": len(self._meta),
                "files": len({m["file"] for m in self._meta}) if self._meta else 0,
                "encoder": "ready" if (self._embeddings is not None) else "empty",
            }

    def clear(self) -> int:
        with self._lock:
            n = len(self._meta)
            self._meta = []
            self._embeddings = None
            self._folder = ""
            self._save()
        return n

    def build(self, folder: str) -> dict:
        if not _NP_OK:
            return {"ok": False, "msg": "numpy missing."}
        encoder = _get_encoder()
        if encoder is None:
            return {"ok": False, "msg": "Encoder unavailable — check 'diagnose'."}
        root = Path(folder).expanduser().resolve()
        if not root.is_dir():
            return {"ok": False, "msg": f"Folder not found: {root}"}

        files = _walk(root)
        chunks: list[str] = []
        meta: list[dict] = []
        for p in files:
            text = _read_text(p)
            if not text:
                continue
            for i, ck in enumerate(_chunk(text)):
                chunks.append(ck)
                # Chunk TEXT rides in the meta so answer() can hand it to
                # the local LLM without re-reading (old indexes lack it —
                # answer() asks for a rebuild).
                meta.append({"file": str(p), "chunk": i, "text": ck})
        if not chunks:
            return {"ok": False, "msg": f"No usable text in {root}."}

        embeddings = encoder.encode(
            chunks, show_progress_bar=False, normalize_embeddings=True
        )
        embeddings = _np.asarray(embeddings, dtype=_np.float32)
        with self._lock:
            self._embeddings = embeddings
            self._meta = meta
            self._folder = str(root)
            self._save()
            self._loaded = True
        return {
            "ok": True,
            "folder": str(root),
            "files": len(files),
            "chunks": len(chunks),
            "msg": (f"Indexed {len(chunks)} chunks across {len(files)} "
                    f"file(s) under {root}."),
        }

    def query(self, q: str, top_k: int = 5) -> list[dict]:
        self._try_load()
        if not _NP_OK:
            return []
        if not q or self._embeddings is None or not self._meta:
            return []
        encoder = _get_encoder()
        if encoder is None:
            return []
        q_emb = encoder.encode([q], normalize_embeddings=True)
        q_emb = _np.asarray(q_emb, dtype=_np.float32)[0]
        with self._lock:
            sims = self._embeddings @ q_emb       # cosine since both normed
            top_idx = list(_np.argsort(-sims)[:top_k])
        out: list[dict] = []
        for i in top_idx:
            i = int(i)
            m = self._meta[i]
            out.append({
                "file": m["file"],
                "chunk": m["chunk"],
                "text": m.get("text", ""),
                "score": float(sims[i]),
            })
        return out


    def answer(self, question: str, top_k: int = 4) -> dict:
        """Retrieval + LOCAL-LLM synthesis with [n] file citations.

        The whole pipeline is on-device: the brain's own sentence encoder
        retrieves, the embedded model writes the answer strictly from the
        retrieved chunks. Returns {"answer": str|None, "sources": [file…],
        "why": str} — answer None when nothing usable was found.
        """
        hits = self.query(question, top_k=top_k)
        hits = [h for h in hits if h["score"] >= 0.25]
        if not hits:
            return {"answer": None, "sources": [],
                    "why": "index empty ya koi matching chunk nahi"}
        if not any(h.get("text") for h in hits):
            return {"answer": None, "sources": [],
                    "why": "purana index format — 'index folder <path>' se "
                           "dobara index banao"}
        sources: list[str] = []
        ctx_lines: list[str] = []
        for h in hits:
            if not h.get("text"):
                continue
            name = os.path.basename(h["file"])
            if name not in sources:
                sources.append(name)
            n = sources.index(name) + 1
            ctx_lines.append(f"[{n}] ({name}) {h['text'][:700]}")
        try:
            from core import local_llm
            out = local_llm.get().generate(
                prompt=("CONTEXT:\n" + "\n\n".join(ctx_lines)
                        + f"\n\nQUESTION: {question}\n\nAnswer the question."),
                system=("Answer ONLY from the CONTEXT chunks. Cite chunk "
                        "numbers like [1]. If the context does not contain "
                        "the answer, say exactly: NOT_IN_DOCS. Keep it under "
                        "5 short sentences. Hinglish is fine."),
                max_tokens=280, temperature=0.2,
            )
        except Exception as e:
            log.debug("[doc_index] answer LLM failed: %s", e)
            out = None
        if not out or "NOT_IN_DOCS" in out:
            return {"answer": None, "sources": sources,
                    "why": "docs mein iska jawab nahi mila"}
        return {"answer": out.strip(), "sources": sources, "why": ""}


def summarize_file(path: str) -> Optional[str]:
    """Local summary of one file (txt/md/pdf/docx/…): parser + embedded
    model, nothing external. None when unreadable or the LLM is absent."""
    p = Path(os.path.expanduser(path.strip().strip('"')))
    if not p.is_file():
        return None
    text = _read_text(p)
    if not text or not text.strip():
        return None
    # Long docs: head + tail carry the thesis and the conclusion.
    if len(text) > 7000:
        text = text[:5000] + "\n…\n" + text[-2000:]
    try:
        from core import local_llm
        return local_llm.get().generate(
            prompt=f"DOCUMENT ({p.name}):\n{text}\n\nSummarise this document.",
            system=("Summarise in 4-6 short lines: what it is, the key "
                    "points, and anything actionable. Hinglish is fine. "
                    "No preamble."),
            max_tokens=260, temperature=0.3,
        )
    except Exception as e:
        log.debug("[doc_index] summarize LLM failed: %s", e)
        return None


_DEFAULT: Optional[DocIndex] = None


def get_doc_index() -> DocIndex:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = DocIndex()
    return _DEFAULT
