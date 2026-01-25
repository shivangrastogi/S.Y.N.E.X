# BACKEND/automations/whatsapp/whatsapp_state.py
"""
GLOBAL WhatsApp automation state
Change values here to control behavior
"""

# 🔒 Master gate — NOTHING sends unless this is True
WHATSAPP_READY = False

# ⏳ Manual delay for WhatsApp Web (seconds)
WHATSAPP_WEB_DELAY = 15

# ⏱ Desktop readiness timeout
WHATSAPP_DESKTOP_TIMEOUT = 40
