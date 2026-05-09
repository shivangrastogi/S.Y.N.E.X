"""Send WhatsApp messages via pywhatkit (uses WhatsApp Web)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from core.skill_registry import skill

try:
    import pywhatkit
    _AVAILABLE = True
except ImportError:
    pywhatkit = None
    _AVAILABLE = False


_ROOT = Path(__file__).resolve().parent.parent
_CONTACTS_FILE = _ROOT / "data" / "contacts.json"


def _load_contacts() -> dict:
    if not _CONTACTS_FILE.exists():
        return {}
    try:
        return json.loads(_CONTACTS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _resolve_phone(name: str) -> str | None:
    contacts = _load_contacts()
    key = name.strip().lower()
    for k, phone in contacts.items():
        if k.lower() == key or key in k.lower():
            return phone if phone.startswith("+") else f"+91{re.sub(r'[^0-9]', '', phone)}"
    return None


@skill(
    name="send_whatsapp",
    description="Send a WhatsApp message to a saved contact (resolves name → phone via data/contacts.json)",
    patterns=[
        "whatsapp pe X ko bolo Y",
        "X ko whatsapp message bhejo Y",
        "send whatsapp to X saying Y",
        "X ko whatsapp kar do",
    ],
    required_entities=["recipient", "message"],
    prompts={
        "recipient": "Kisko message bhejna hai?",
        "message":   "Kya likhna hai message mein?",
    },
)
def send_whatsapp(slots: dict) -> str:
    if not _AVAILABLE:
        return "pywhatkit install nahi hai. 'pip install pywhatkit' chalao."

    recipient = (slots.get("recipient") or "").strip()
    message = (slots.get("message") or "").strip()
    if not recipient or not message:
        return "Recipient aur message dono chahiye."

    phone = _resolve_phone(recipient)
    if not phone:
        return f"'{recipient}' contacts.json mein nahi hai. data/contacts.json mein add karo."

    fire = datetime.now() + timedelta(minutes=1)
    try:
        pywhatkit.sendwhatmsg(
            phone_no=phone,
            message=message,
            time_hour=fire.hour,
            time_min=fire.minute,
            wait_time=15,
            tab_close=True,
        )
    except Exception as e:
        return f"WhatsApp send fail ho gaya: {e}"
    return f"{recipient} ko message bheja: {message[:50]}{'...' if len(message) > 50 else ''}"
