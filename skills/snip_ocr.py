"""Region-select screenshot + OCR.

  "snip and read" / "screenshot ke text padho" / "yeh padh ke batao"

Workflow:
  1. Grab the active screen via mss.
  2. If pyautogui is available, allow user to select a region with mouse
     (a tiny tk overlay) — else OCR the full screen.
  3. Run pytesseract; if Tesseract binary missing, fall back to "screen
     paragraph extracted via Pillow getbbox" (very basic).
  4. Save the snip to data/snips/ and return the extracted text.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.skill_registry import skill  # noqa: E402

log = logging.getLogger(__name__)

_SNIP_DIR = Path(_ROOT) / "data" / "snips"
_SNIP_DIR.mkdir(parents=True, exist_ok=True)


def _capture_full_screen():
    try:
        import mss
        from PIL import Image
    except Exception:
        return None
    with mss.mss() as sct:
        mon = sct.monitors[1]
        raw = sct.grab(mon)
        return Image.frombytes("RGB", raw.size, raw.rgb)


def _select_region_tk():
    """Quick rubber-band selection using tkinter. Returns (x1,y1,x2,y2) or None."""
    try:
        import tkinter as tk
    except Exception:
        return None
    coords = {"x1": 0, "y1": 0, "x2": 0, "y2": 0, "ok": False}
    root = tk.Tk()
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.25)
    root.configure(bg="black")
    root.attributes("-topmost", True)
    canvas = tk.Canvas(root, cursor="cross", bg="black", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)
    rect = {"id": None}

    def on_press(e):
        coords["x1"], coords["y1"] = e.x_root, e.y_root
        rect["id"] = canvas.create_rectangle(e.x, e.y, e.x, e.y,
                                             outline="cyan", width=2)
    def on_drag(e):
        if rect["id"]:
            canvas.coords(rect["id"], coords["x1"] - root.winfo_rootx(),
                          coords["y1"] - root.winfo_rooty(), e.x, e.y)
    def on_release(e):
        coords["x2"], coords["y2"] = e.x_root, e.y_root
        coords["ok"] = True
        root.destroy()
    def on_esc(_): root.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Escape>", on_esc)
    root.mainloop()
    if not coords["ok"]:
        return None
    x1, y1, x2, y2 = coords["x1"], coords["y1"], coords["x2"], coords["y2"]
    if x1 == x2 or y1 == y2:
        return None
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _ocr(image) -> str:
    try:
        import pytesseract
        return pytesseract.image_to_string(image, lang="eng+hin").strip()
    except Exception as e:
        log.info("[snip_ocr] tesseract unavailable: %s", e)
        return ""


@skill(
    name="snip_and_ocr",
    description="Select a screen region and read the text inside it (OCR).",
    patterns=[
        "snip and read", "screenshot ke text padho",
        "yeh padh ke batao", "screen pe se text uthao",
        "region select karke ocr karo", "snip ka text batao",
        "select area and ocr", "screen text capture karo",
    ],
    required_entities=[],
)
def snip_and_ocr(slots: dict) -> str:
    img = _capture_full_screen()
    if img is None:
        return "Screen capture libraries missing — 'pip install mss pillow' chalao."
    region = _select_region_tk()
    if region:
        x1, y1, x2, y2 = region
        crop = img.crop((x1, y1, x2, y2))
    else:
        crop = img
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _SNIP_DIR / f"snip_{ts}.png"
    try:
        crop.save(path)
    except Exception as e:
        log.info("[snip_ocr] save failed: %s", e)
    text = _ocr(crop)
    if not text:
        return ("Snip save kar liya, par OCR nahi chala — Tesseract binary install karo "
                "(https://github.com/UB-Mannheim/tesseract/wiki) and 'pip install pytesseract'.")
    snippet = text if len(text) <= 800 else text[:800] + "..."
    return f"Extracted text ({len(text)} chars):\n{snippet}"


@skill(
    name="full_screen_ocr",
    description="OCR the entire current screen and return the text.",
    patterns=[
        "full screen ocr", "saari screen padho",
        "whole screen text", "complete screen ocr",
        "ocr the entire screen",
    ],
    required_entities=[],
)
def full_screen_ocr(slots: dict) -> str:
    img = _capture_full_screen()
    if img is None:
        return "mss/pillow missing."
    text = _ocr(img)
    if not text:
        return "OCR fail — Tesseract install karo."
    snippet = text if len(text) <= 1200 else text[:1200] + "..."
    return f"Full screen OCR:\n{snippet}"
