"""Screen ACTIONS — AERIS acts on what it sees. High-accuracy v2.

Screen-aware v1 (core/screen_agent.py) explained the screen. This DOES
things on it — click, scroll, type — and aims for near-100% click
accuracy through five layers:

  1. DPI-scale conversion   OCR gives PHYSICAL pixels; pyautogui clicks in
                            LOGICAL pixels. On a 150% display those differ
                            by 1.5x — the #1 mis-click cause. We compute the
                            scale and convert every coordinate.
  2. Active-window-only OCR We OCR just the foreground window's rectangle,
                            not the whole busy desktop — far less noise,
                            the target is almost always there, and faster.
  3. Confidence filtering   Tesseract reports per-word confidence; we drop
                            garbage words (< _MIN_CONF) so "wrroren" noise
                            never becomes a click target.
  4. Image preprocessing    2x upscale + grayscale before OCR → crisp UI
                            text reads reliably (coords divided back by 2).
  5. Smart disambiguation   Prefer short button-like phrases + exact/word
                            matches over text buried in paragraphs; among
                            ties, the topmost-leftmost.

``locate_target`` returns the match WITHOUT clicking (dry run) so callers
can confirm; ``click_target`` locates then clicks.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

_MIN_CONF = 45          # drop OCR words below this confidence
_UPSCALE = 2            # OCR on a 2x image reads small UI text far better
_FUZZY_ACCEPT = 82      # min fuzzy score to act on a non-exact match


def _available() -> bool:
    try:
        import mss, pytesseract, pyautogui  # noqa: F401
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False


# ── DPI scale (physical → logical) ───────────────────────────────────
def _scale() -> float:
    """physical_px / logical_px. 1.0 when the process is DPI-aware or the
    display is at 100%. mss reports physical; pyautogui clicks logical."""
    try:
        import mss, pyautogui
        with mss.mss() as sct:
            phys_w = sct.monitors[1]["width"]
        log_w = pyautogui.size().width
        s = phys_w / log_w if log_w else 1.0
        # Guard against nonsense (e.g. transient 0); clamp to sane range.
        return s if 0.5 <= s <= 4.0 else 1.0
    except Exception:
        return 1.0


# ── capture (active window preferred) ────────────────────────────────
def _active_window_rect() -> Optional[tuple[int, int, int, int]]:
    """Foreground window rect in PHYSICAL pixels (left, top, w, h)."""
    try:
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        try:  # per-monitor DPI aware rect if available
            ctypes.windll.shcore  # noqa: probe
        except Exception:
            pass
        hwnd = u32.GetForegroundWindow()
        if not hwnd:
            return None
        r = wintypes.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = r.right - r.left, r.bottom - r.top
        if w < 40 or h < 40:
            return None
        return (r.left, r.top, w, h)
    except Exception:
        return None


def _capture(active_only: bool = True):
    """(PIL image, origin_left, origin_top) in PHYSICAL pixels."""
    try:
        import mss
        from PIL import Image
        with mss.mss() as sct:
            if active_only:
                rect = _active_window_rect()
                if rect:
                    left, top, w, h = rect
                    mon = {"left": left, "top": top, "width": w, "height": h}
                    raw = sct.grab(mon)
                    return (Image.frombytes("RGB", raw.size, raw.rgb),
                            left, top)
            mon = sct.monitors[1]
            raw = sct.grab(mon)
            return (Image.frombytes("RGB", raw.size, raw.rgb),
                    mon.get("left", 0), mon.get("top", 0))
    except Exception as e:
        log.info("[screen_actions] capture failed: %s", e)
        return None, 0, 0


# ── OCR → confident line phrases ─────────────────────────────────────
def _line_phrases(data: dict, conf_min: int = _MIN_CONF, downscale: int = 1):
    """Group confident OCR words into per-line phrases with a merged box.
    Coords are divided by ``downscale`` (undo the OCR upscaling).
    Returns list of dicts: {phrase, cx, cy, w, conf}."""
    lines: dict = {}
    n = len(data["text"])
    for i in range(n):
        word = (data["text"][i] or "").strip()
        if not word:
            continue
        try:
            conf = float(data["conf"][i])
        except Exception:
            conf = -1
        if conf < conf_min:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        x, y = data["left"][i], data["top"][i]
        w, h = data["width"][i], data["height"][i]
        e = lines.setdefault(key, {"words": [], "x1": x, "y1": y,
                                   "x2": x + w, "y2": y + h,
                                   "conf": [], "nchar": 0})
        e["words"].append(word)
        e["conf"].append(conf)
        e["nchar"] += len(word)
        e["x1"] = min(e["x1"], x); e["y1"] = min(e["y1"], y)
        e["x2"] = max(e["x2"], x + w); e["y2"] = max(e["y2"], y + h)
    out = []
    for e in lines.values():
        phrase = " ".join(e["words"])
        cx = ((e["x1"] + e["x2"]) // 2) // downscale
        cy = ((e["y1"] + e["y2"]) // 2) // downscale
        out.append({
            "phrase": phrase, "cx": cx, "cy": cy,
            "nchar": e["nchar"],
            "conf": sum(e["conf"]) / len(e["conf"]) if e["conf"] else 0,
        })
    return out


def _words(data: dict, conf_min: int = _MIN_CONF, downscale: int = 1):
    """Individual confident words with their OWN box centres — so a target
    that matches one word in a shared line (menu/toolbar) is clicked ON
    that word, not the line's midpoint."""
    out = []
    for i in range(len(data["text"])):
        w = (data["text"][i] or "").strip()
        if not w:
            continue
        try:
            conf = float(data["conf"][i])
        except Exception:
            conf = -1
        if conf < conf_min:
            continue
        x, y = data["left"][i], data["top"][i]
        ww, hh = data["width"][i], data["height"][i]
        out.append({
            "phrase": w,
            "cx": (x + ww // 2) // downscale,
            "cy": (y + hh // 2) // downscale,
            "nchar": len(w), "conf": conf,
        })
    return out


def _elements(active_only: bool = True):
    """(line_phrases, word_elements, origin_left, origin_top)."""
    img, ox, oy = _capture(active_only)
    if img is None:
        return [], [], 0, 0
    try:
        import pytesseract
        from PIL import Image
        big = img
        if _UPSCALE > 1:
            big = img.resize((img.width * _UPSCALE, img.height * _UPSCALE),
                             Image.LANCZOS).convert("L")
        data = pytesseract.image_to_data(
            big, lang="eng+hin", output_type=pytesseract.Output.DICT)
    except Exception as e:
        log.info("[screen_actions] OCR failed: %s", e)
        return [], [], ox, oy
    return (_line_phrases(data, downscale=_UPSCALE),
            _words(data, downscale=_UPSCALE), ox, oy)


# ── locate (dry run) + click ─────────────────────────────────────────
def _score(target: str, phrase: str) -> float:
    """0-100 match score with a brevity/word bonus so short button-like
    phrases beat a match buried in a long paragraph."""
    t, p = target.lower().strip(), phrase.lower().strip()
    if not p:
        return 0.0
    if t == p:
        return 100.0
    base = 0.0
    words = p.split()
    if t in words:                       # target is a whole word on the line
        base = 92.0
    elif t in p:                         # substring
        base = 84.0
    else:
        try:
            from rapidfuzz import fuzz
            base = float(fuzz.partial_ratio(t, p))
        except Exception:
            base = 0.0
    # Brevity bonus: prefer concise UI labels (buttons/links).
    brevity = max(0.0, 8.0 - 0.4 * len(words))
    return min(100.0, base + brevity)


def locate_target(target: str, active_only: bool = True) -> Optional[dict]:
    """Best on-screen match for ``target`` WITHOUT clicking. Returns
    {phrase, x, y, score, conf} in click (logical) coordinates, or None.

    Search order for accuracy:
      * a single-word target → match WORD boxes first, so the click lands
        exactly on that word (menus/toolbars share a line);
      * else / no word hit → match LINE phrases (multi-word labels).
    Ties break to the topmost-leftmost (menus/buttons sit high). Active
    window first, then the whole screen."""
    target = (target or "").strip()
    if not target or not _available():
        return None
    single = len(target.split()) == 1
    scale = _scale()
    for scope in ([True, False] if active_only else [False]):
        lines, words, ox, oy = _elements(scope)
        candidates = []
        if single and words:
            candidates = words                 # click the exact word
        if not candidates:
            candidates = lines
        # If single-word yields a weak word hit, also let lines compete.
        pool = candidates + (lines if (single and candidates is words) else [])
        if not pool:
            continue
        scored = sorted(
            ((_score(target, e["phrase"]), e) for e in pool),
            key=lambda se: (-se[0], se[1]["cy"], se[1]["cx"]))
        best_score, best = scored[0]
        if best_score >= _FUZZY_ACCEPT:
            return {
                "phrase": best["phrase"].strip(),
                "x": int((ox + best["cx"]) / scale),
                "y": int((oy + best["cy"]) / scale),
                "score": round(best_score, 1),
                "conf": round(best["conf"], 1),
            }
    return None


def click_target(target: str, *, double: bool = False) -> str:
    if not _available():
        return ("Screen actions ke liye pyautogui + pytesseract + mss "
                "chahiye — 'dep check' karo.")
    if not (target or "").strip():
        return "Kis cheez pe click karun? Naam batao."
    hit = locate_target(target)
    if not hit:
        return f"'{target}' screen pe reliably nahi mila — thoda aur clearly batao."
    try:
        import pyautogui
        pyautogui.click(hit["x"], hit["y"], clicks=2 if double else 1)
    except Exception as e:
        return f"Click fail: {e}"
    return (f"'{hit['phrase'][:40]}' pe click kiya ✓ "
            f"(match {hit['score']}%, ocr-conf {hit['conf']}%)")


def scroll(direction: str = "down", amount: int = 500) -> str:
    if not _available():
        return "pyautogui nahi hai."
    import pyautogui
    d = (direction or "down").lower()
    clicks = -amount if ("down" in d or "neeche" in d or "niche" in d) else amount
    try:
        pyautogui.scroll(clicks)
    except Exception as e:
        return f"Scroll fail: {e}"
    return f"Screen {'neeche' if clicks < 0 else 'upar'} scroll kiya."


def type_text(text: str) -> str:
    if not _available():
        return "pyautogui nahi hai."
    if not text:
        return "Kya type karna hai? Batao."
    import pyautogui
    try:
        pyautogui.typewrite(text, interval=0.01)
    except Exception as e:
        return f"Type fail: {e}"
    return f"Type kar diya: '{text[:40]}'"


# ── LLM-picked click for vague instructions ──────────────────────────
def smart_click(instruction: str, user_name: str = "sir") -> str:
    lines, words, ox, oy = _elements(active_only=True)
    elems = lines
    if not elems:
        return "Screen padh nahi paaya."
    try:
        from core import local_llm
        llm = local_llm.get()
        if not llm.available():
            return click_target(instruction)
        numbered = "\n".join(f"{i}: {e['phrase'][:50]}"
                             for i, e in enumerate(elems[:40]))
        messages = [
            {"role": "system", "content":
                "You pick which on-screen element the user wants to click. "
                "Reply with ONLY the number of the best matching element. "
                "If none fit, reply -1."},
            {"role": "user", "content":
                f"Elements:\n{numbered}\n\nUser wants to: {instruction}\n"
                "Number:"},
        ]
        raw = (llm.chat(messages, max_tokens=8) or "").strip()
        m = re.search(r"-?\d+", raw)
        idx = int(m.group()) if m else -1
        if idx < 0 or idx >= len(elems):
            return click_target(instruction)
        e = elems[idx]
        scale = _scale()
        import pyautogui
        pyautogui.click(int((ox + e["cx"]) / scale), int((oy + e["cy"]) / scale))
        return f"'{e['phrase'].strip()[:40]}' pe click kiya ✓ (samajh ke)"
    except Exception as ex:
        log.warning("[screen_actions] smart_click failed: %s", ex)
        return click_target(instruction)
