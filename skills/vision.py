"""Screen OCR + click-by-text. Needs Tesseract binary + python packages mss & pytesseract."""

from __future__ import annotations

from core.skill_registry import skill

try:
    import mss
    import pytesseract
    from PIL import Image
    _AVAILABLE = True
except ImportError:
    mss = None
    pytesseract = None
    Image = None
    _AVAILABLE = False

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    pyautogui = None
    _PYAUTOGUI = False


def _grab_screen() -> "Image.Image | None":
    if not _AVAILABLE:
        return None
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.rgb)


@skill(
    name="read_screen",
    description="OCR the visible screen and return all extracted text",
    patterns=[
        "screen padho",
        "yeh screen padh do",
        "read this screen",
        "ocr the screen",
        "screen pe kya likha hai",
    ],
    required_entities=[],
)
def read_screen(_slots: dict) -> str:
    if not _AVAILABLE:
        return "Vision modules install nahi hain. 'pip install mss pytesseract pillow' aur Tesseract binary chahiye."
    img = _grab_screen()
    if img is None:
        return "Screen capture fail."
    text = pytesseract.image_to_string(img, lang="eng+hin").strip()
    if not text:
        return "Screen pe koi readable text nahi mila."
    snippet = text[:600] + ("..." if len(text) > 600 else "")
    return f"Screen text: {snippet}"


@skill(
    name="click_text",
    description="Find a piece of text on the screen and click its center",
    patterns=[
        "X pe click karo",
        "click on X",
        "X button dabao",
        "X par click kar do",
    ],
    required_entities=["query"],
    prompts={"query": "Kis text pe click karna hai?"},
)
def click_text(slots: dict) -> str:
    if not (_AVAILABLE and _PYAUTOGUI):
        return "Vision + pyautogui dono chahiye is feature ke liye."
    target = (slots.get("query") or "").strip().lower()
    if not target:
        return "Kis text pe click karna hai? Batao."

    img = _grab_screen()
    if img is None:
        return "Screen capture fail."

    data = pytesseract.image_to_data(img, lang="eng+hin", output_type=pytesseract.Output.DICT)
    for i, word in enumerate(data["text"]):
        if word and target in word.lower():
            x = data["left"][i] + data["width"][i] // 2
            y = data["top"][i] + data["height"][i] // 2
            pyautogui.click(x, y)
            return f"'{word}' pe click kiya."
    return f"'{target}' screen pe nahi mila."
