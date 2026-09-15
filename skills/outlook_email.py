"""Outlook email compose via win32com.

Opens a draft window (does NOT auto-send) — safer for voice commands.
The user can review and click Send themselves.

Skills:
  * ``compose_email`` — "compose email to <recipient> about <subject>"
                        / "email <recipient> subject <subj> body <body>"
  * ``email_draft_blank`` — open an empty draft
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from core.skill_registry import skill

log = logging.getLogger(__name__)


_OL_MAIL_ITEM = 0


def _open_outlook():
    try:
        import win32com.client  # type: ignore
    except Exception as e:
        log.info("[outlook_email] win32com unavailable: %s", e)
        return None
    try:
        return win32com.client.Dispatch("Outlook.Application")
    except Exception as e:
        log.info("[outlook_email] dispatch failed: %s", e)
        return None


# Recipient / subject / body parsing patterns. Each is optional; we use
# whatever the user actually says. Recipient defaults to empty so the
# user fills it in after the draft window opens.
_RECIPIENT_RE = re.compile(
    r"\bto\s+"
    r"(?P<who>"
    r"[\w.+\-]+@[\w.\-]+\.[a-z]{2,}"   # email address, or
    r"|[A-Za-z][\w.\-']{1,40}"          # bare name (single word, no spaces)
    r")"
    r"(?=\s+(?:subject|about|re:|regarding|body|with|saying|that|$)|[,;.]|$)",
    re.IGNORECASE,
)
_SUBJECT_RE = re.compile(
    r"\b(?:subject|about|re:|regarding)\s+(?P<subj>.+?)"
    r"(?=\s+(?:body|with\s+body|saying|that\s+says)\b|$)",
    re.IGNORECASE,
)
_BODY_RE = re.compile(
    r"\b(?:body|with\s+body|saying|that\s+says)\s+(?P<body>.+)$",
    re.IGNORECASE,
)


def _parse(text: str) -> tuple[str, str, str]:
    recipient = subject = body = ""
    if not text:
        return recipient, subject, body
    m = _RECIPIENT_RE.search(text)
    if m:
        recipient = m.group("who").strip()
    m = _SUBJECT_RE.search(text)
    if m:
        subject = m.group("subj").strip(" .,?\"'")
    m = _BODY_RE.search(text)
    if m:
        body = m.group("body").strip(" .,?\"'")
    return recipient, subject, body


# ── compose_email ──────────────────────────────────────────────────


@skill(
    name="compose_email",
    description="Open an Outlook draft window pre-filled with recipient / "
                "subject / body parsed from your voice. Does NOT send.",
    patterns=[
        "compose email", "write email", "draft email",
        "email karo", "mail kar do",
        "email someone", "send email to",
        "compose email to", "draft email to",
        "write email about", "email subject",
    ],
    required_entities=[],
)
def compose_email(slots: dict) -> str:
    text = slots.get("raw_text") or slots.get("text") or ""
    recipient, subject, body = _parse(text)

    outlook = _open_outlook()
    if outlook is None:
        return ("Outlook reach nahi ho paya. Outlook installed hai? "
                "pywin32 also needed.")
    try:
        mail = outlook.CreateItem(_OL_MAIL_ITEM)
        if recipient:
            mail.To = recipient
        if subject:
            mail.Subject = subject
        if body:
            # HTMLBody preserves line breaks better; convert plain to <p>.
            mail.HTMLBody = "<p>" + body.replace("\n", "</p><p>") + "</p>"
        mail.Display(False)   # False = non-modal, user can still control AERIS
    except Exception as e:
        return f"Email draft fail: {e}"

    parts = []
    if recipient: parts.append(f"to {recipient}")
    if subject:   parts.append(f"subject '{subject}'")
    if body:      parts.append(f"body {len(body)} chars")
    return ("Outlook draft khol diya"
            + (f" ({', '.join(parts)})" if parts else "")
            + ". Send tum khud kar do.")


# ── email_draft_blank ──────────────────────────────────────────────


@skill(
    name="email_draft_blank",
    description="Open an empty Outlook draft window.",
    patterns=[
        "blank email", "new email", "new outlook email",
        "open new email", "new mail kholo",
        "blank draft", "naya email",
    ],
    required_entities=[],
)
def email_draft_blank(_slots: dict) -> str:
    outlook = _open_outlook()
    if outlook is None:
        return "Outlook reach nahi ho paya."
    try:
        mail = outlook.CreateItem(_OL_MAIL_ITEM)
        mail.Display(False)
    except Exception as e:
        return f"Email draft fail: {e}"
    return "Outlook draft khol diya — sab kuch tum bhar do."
