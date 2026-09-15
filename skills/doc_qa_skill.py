"""Document-QA voice surface.

Skills:
  * ``doc_index_folder``  — "index folder C:\\Notes" / "index my documents"
  * ``doc_query``         — "doc query budget Q1" / "search docs for budget Q1"
  * ``doc_status``        — current index size + folder
  * ``doc_clear``         — wipe the index
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from core.skill_registry import skill

log = logging.getLogger(__name__)


_PATH_RE = re.compile(
    r"(?:index|folder)\s+(?P<p>[A-Za-z]:[\\\/][^\"'\n]+|~[\\\/][^\"'\n]+|[\\\/][^\"'\n]+)",
    re.IGNORECASE,
)
_KEYWORD_FOLDERS = {
    "documents": "~/Documents",
    "downloads": "~/Downloads",
    "desktop":   "~/Desktop",
    "pictures":  "~/Pictures",
    "notes":     "data/notes",
}


def _resolve_folder(text: str) -> str:
    if not text:
        return ""
    m = _PATH_RE.search(text)
    if m:
        return m.group("p").strip()
    lo = text.lower()
    for kw, folder in _KEYWORD_FOLDERS.items():
        if kw in lo:
            return folder
    return ""


def _strip_verb(text: str) -> str:
    # ``\s*`` (not ``\s+``) so a bare verb alone strips to empty — the
    # skill then prompts for a query instead of treating the trigger as
    # the search term.
    return re.sub(
        r"^(?:please\s+)?"
        r"(?:doc\s+query|doc\s+search|search\s+docs?\s+for|query\s+docs?|"
        r"docs?\s+search|docs?\s+query|doc\s+ask|ask\s+the\s+docs?)\s*",
        "", (text or "").strip(), flags=re.IGNORECASE,
    ).strip(" ?\"'")


@skill(
    name="doc_index_folder",
    description="Walk a folder + embed every text file into the doc-QA index.",
    patterns=[
        "index folder", "doc index folder", "index documents",
        "index my documents", "index notes",
        "build doc index", "index downloads",
        "scan folder for docs", "docs index karo",
    ],
    required_entities=[],
)
def doc_index_folder(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    folder = _resolve_folder(text)
    if not folder:
        return ("Folder do — e.g. 'index folder C:\\Notes' or "
                "'index my documents'.")
    try:
        from core.doc_index import get_doc_index
    except Exception as e:
        return f"doc_index load fail: {e}"
    info = get_doc_index().build(folder)
    return info.get("msg") or "Index build done."


@skill(
    name="doc_query",
    description="Search the indexed documents for a query — returns top "
                "matching files + chunk indices.",
    patterns=[
        "doc query", "search docs for", "query docs",
        "ask the docs", "docs me dhundo", "search my docs for",
        "doc search", "doc ask",
    ],
    required_entities=[],
)
def doc_query(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    q = _strip_verb(text)
    if not q:
        return "Query do — e.g. 'search docs for budget'."
    try:
        from core.doc_index import get_doc_index
    except Exception as e:
        return f"doc_index load fail: {e}"
    hits = get_doc_index().query(q, top_k=5)
    if not hits:
        stats = get_doc_index().stats()
        if stats.get("chunks", 0) == 0:
            return "Index khaali hai — pehle 'index folder X' run karo."
        return f"'{q}' ke koi matches nahi mile (index size: {stats['chunks']} chunks)."
    lines = [f"Top {len(hits)} match(es) for '{q}':"]
    for h in hits:
        lines.append(f"  • {h['score']:.2f}  {h['file']}#chunk{h['chunk']}")
    return "\n".join(lines)


@skill(
    name="doc_status",
    description="Report current doc-QA index size + indexed folder.",
    patterns=[
        "doc status", "doc index status", "docs status",
        "doc index info", "doc index size",
        "doc index kya hai", "docs index kahan se hai",
    ],
    required_entities=[],
)
def doc_status(_slots: dict) -> str:
    try:
        from core.doc_index import get_doc_index
    except Exception as e:
        return f"doc_index load fail: {e}"
    st = get_doc_index().stats()
    if not st.get("chunks"):
        return "Doc index khaali hai — 'index folder X' to populate."
    return (f"Doc index: {st['chunks']} chunks across {st['files']} file(s) "
            f"from {st['folder']}.")


@skill(
    name="doc_clear",
    description="Wipe the document-QA index.",
    patterns=[
        "doc clear", "clear doc index", "wipe doc index",
        "doc index clear", "docs clear karo",
        "reset doc index",
    ],
    required_entities=[],
)
def doc_clear(_slots: dict) -> str:
    try:
        from core.doc_index import get_doc_index
    except Exception as e:
        return f"doc_index load fail: {e}"
    n = get_doc_index().clear()
    return f"Cleared {n} chunk(s) from the doc index."


# ── Doc Brain v2 — standalone answers + summaries (local LLM only) ──── #

_ANSWER_STRIP_RE = re.compile(
    r"^(?:docs?\s+se\s+(?:batao|jawab\s+do)|documents?\s+se\s+batao|"
    r"docs?\s+ke\s+hisaa?b\s+se|notes?\s+ke\s+hisaa?b\s+se(?:\s+batao)?|"
    r"doc\s+answer|answer\s+from\s+docs?)\s*",
    re.IGNORECASE,
)

_SUMMARY_STRIP_RE = re.compile(
    r"^(?:is\s+file\s+ka\s+summary(?:\s+do)?|file\s+ka\s+summary(?:\s+do)?|"
    r"file\s+summarize\s+karo|summarize\s+file|summarise\s+file|"
    r"document\s+ka\s+summary(?:\s+do)?|file\s+ka\s+saar\s+batao)\s*",
    re.IGNORECASE,
)


@skill(
    name="doc_answer",
    description="Answer a question FROM the indexed documents (local retrieval + embedded LLM, with citations).",
    patterns=[
        "docs se batao", "documents se batao", "docs se jawab do",
        "docs ke hisaab se", "notes ke hisaab se batao",
        "doc answer", "answer from docs", "mere documents me kya likha hai",
    ],
    required_entities=[],
)
def doc_answer(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    question = _ANSWER_STRIP_RE.sub("", text).strip(" ?\"'")
    if not question:
        return ("Kya poochna hai docs se? Jaise: 'docs se batao project ka "
                "deadline kya hai'.")
    try:
        from core.doc_index import get_doc_index
        res = get_doc_index().answer(question)
    except Exception as e:
        log.warning("[doc_answer] failed: %s", e)
        return "Doc brain abhi jawab nahi de paya, sir."
    if not res.get("answer"):
        why = res.get("why") or "kuch nahi mila"
        hint = (" Pehle 'index folder <path>' se index banao."
                if "index empty" in why else "")
        return f"Docs mein iska jawab nahi mila, sir.{hint}"
    src = ", ".join(res.get("sources") or [])
    return res["answer"] + (f"  (sources: {src})" if src else "")


@skill(
    name="file_summary",
    description="Summarise one file (txt/md/pdf/docx) fully on-device with the embedded LLM.",
    patterns=[
        "file ka summary do", "is file ka summary do", "file summarize karo",
        "summarize file", "summarise file", "document ka summary do",
        "file ka saar batao", "pdf ka summary do",
    ],
    required_entities=[],
)
def file_summary(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    target = _SUMMARY_STRIP_RE.sub("", text).strip(" ?\"'")
    m = re.search(r"[A-Za-z]:[\\/][^\"'\n]+|~[\\/][^\"'\n]+", text)
    if m:
        target = m.group(0).strip()
    if not target:
        return ("Kaunsi file, sir? Path do — jaise: 'file ka summary do "
                "C:\\Notes\\plan.pdf'.")
    try:
        from core.doc_index import summarize_file
        out = summarize_file(target)
    except Exception as e:
        log.warning("[file_summary] failed: %s", e)
        out = None
    if not out:
        return (f"'{target}' read ya summarise nahi ho paya — path check "
                "karo (txt/md/pdf/docx chalta hai).")
    return out
