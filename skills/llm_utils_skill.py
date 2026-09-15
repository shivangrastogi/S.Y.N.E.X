"""Local-LLM utilities — grammar fix, brainstorm, explain-simply.

Uses AERIS's OWN embedded model (core/local_llm.generate — persona-free,
in-process llama.cpp). No API, no network. Each strips its command phrase
to isolate the payload, then asks the local model.
"""
from __future__ import annotations

import logging
import re

from core.skill_registry import skill

log = logging.getLogger(__name__)

_MAX_IN = 2000


def _gen(prompt: str, system: str, max_tokens: int = 260) -> str | None:
    try:
        from core import local_llm
        llm = local_llm.get()
        if not llm.available():
            return None
        return llm.generate(prompt=prompt, system=system,
                            max_tokens=max_tokens, temperature=0.4)
    except Exception as e:
        log.debug("[llm_utils] generate failed: %s", e)
        return None


def _strip(raw: str, pattern: str) -> str:
    # count=1: strip only the leading command phrase. Without it, a payload
    # ending in a keyword ("…ke ideas") would match a SECOND time and get
    # deleted too.
    body = re.sub(pattern, "", raw or "", count=1,
                  flags=re.IGNORECASE).strip(" :\"'?.")
    return body[:_MAX_IN]


def _drop_words(raw: str, cmd: set) -> str:
    """Remove command/filler tokens from anywhere — robust when the payload
    comes BEFORE the command phrase ("<topic> ke fayde nuksan batao")."""
    keep = [t for t in (raw or "").split()
            if t.lower().strip(":-?\"'.") not in cmd]
    return " ".join(keep).strip(" :\"'?.")[:_MAX_IN]


_NO_MODEL = ("Iske liye local model chahiye — data/models/llm/ mein ek "
             ".gguf daal do, phir bina internet ke chalega.")


@skill(
    name="fix_grammar",
    description="Fix the grammar of a sentence using the local model (offline).",
    patterns=[
        "grammar theek karo", "iski grammar fix karo", "ye sentence sahi karo",
        "grammar check karo is line ki", "is line ko sahi likho",
        "grammar sudhaaro", "sentence correct karo",
    ],
    required_entities=[],
)
def fix_grammar(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _strip(raw,
                  r".*?(?:grammar|sentence|line|is\s*line)\s*"
                  r"(?:theek|fix|sahi|check|sudhaaro?|correct|ko)?\s*"
                  r"(?:karo|likho|kar\s*do)?\s*[:\-]?\s*")
    if len(body) < 3:
        return ("Kaunsa sentence theek karun, sir? Bolo 'grammar theek karo "
                "<sentence>'.")
    out = _gen(f"Sentence: {body}",
               system=("Fix ONLY the grammar and spelling of the sentence. "
                       "Keep the meaning and language. Reply with just the "
                       "corrected sentence, nothing else."))
    return out.strip() if out else _NO_MODEL


@skill(
    name="brainstorm_ideas",
    description="Brainstorm a few ideas on a topic using the local model (offline).",
    patterns=[
        "brainstorm karo ideas", "ideas do", "mujhe ideas do",
        "kuch ideas suggest karo", "is topic pe ideas do",
        "creative ideas batao", "ideas chahiye is baare me",
    ],
    required_entities=[],
)
def brainstorm_ideas(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _strip(raw,
                  r".*?(?:brainstorm|ideas?|suggest|creative)\s*"
                  r"(?:karo|do|chahiye|batao|suggest)?\s*"
                  r"(?:is\s*(?:topic|baare)\s*(?:pe|me)?)?\s*[:\-]?\s*")
    if len(body) < 3:
        return ("Kis baare mein ideas chahiye, sir? Jaise 'brainstorm karo "
                "weekend trip ke ideas'.")
    out = _gen(f"Topic: {body}",
               system=("Give 4-5 short, distinct ideas as a simple list, one "
                       "per line starting with '- '. Hinglish theek hai. "
                       "Keep each idea to one line."), max_tokens=280)
    return out.strip() if out else _NO_MODEL


@skill(
    name="explain_simply",
    description="Explain a concept in simple words using the local model (offline).",
    patterns=[
        "simple bhasha me samjhao", "ye concept samjhao",
        "asaan shabdon me batao", "isko simple me explain karo",
        "aasan bhasha me samjhao", "ye kya hota hai simple me",
        "bacho ki tarah samjhao",
    ],
    required_entities=[],
)
def explain_simply(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _strip(raw,
                  r".*?(?:simple|asaan|aasan|easy|bacho\s*ki\s*tarah)?\s*"
                  r"(?:bhasha|shabdon|words|me|mein)?\s*"
                  r"(?:me|mein)?\s*(?:explain|samjhao|samjha\s*do|batao)\s*"
                  r"(?:karo|do)?\s*[:\-]?\s*")
    if len(body) < 3:
        return ("Kya samjhau, sir? Jaise 'simple bhasha me samjhao blockchain "
                "kya hai'.")
    out = _gen(f"Concept: {body}",
               system=("Explain the concept in 3-4 short, simple sentences a "
                       "beginner would understand. Use a small everyday "
                       "analogy if it helps. Hinglish theek hai."))
    return out.strip() if out else _NO_MODEL


@skill(
    name="make_title",
    description="Suggest a short title/heading for some text (offline local model).",
    patterns=[
        "iska title banao", "ek acha title suggest karo", "heading banao",
        "title generate karo", "iske liye title do",
        "ek headline banao is baare me", "achha sa title chahiye",
    ],
    required_entities=[],
)
def make_title(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _strip(raw,
                  r".*?(?:ek\s*(?:acha|achha)?\s*)?(?:title|heading|headline)\s*"
                  r"(?:suggest|banao|generate|do|chahiye)?\s*"
                  r"(?:karo|do)?\s*(?:is\s*(?:liye|baare)\s*(?:me|pe)?)?\s*"
                  r"[:\-]?\s*")
    if len(body) < 3:
        return ("Kis baare mein title, sir? Text ya topic do — jaise 'iska "
                "title banao <text>'.")
    out = _gen(f"Text: {body}",
               system=("Suggest ONE short, catchy title (max 8 words) for the "
                       "text. Reply with just the title, no quotes."),
               max_tokens=40)
    return out.strip().strip('"') if out else _NO_MODEL


@skill(
    name="shorten_text",
    description="Shorten text to a crisp one-line TL;DR (offline local model).",
    patterns=[
        "isko chhota karo", "tldr do", "short karo ye", "summary chhoti karo",
        "ek line me batao", "isko sankshep me likho", "tldr banao",
    ],
    required_entities=[],
)
def shorten_text(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _strip(raw,
                  r".*?(?:isko|is\s*ko|ye|is)?\s*"
                  r"(?:chhota|short|sankshep|tldr|ek\s*line)\s*"
                  r"(?:me|mein)?\s*(?:karo|do|banao|likho|batao)?\s*[:\-]?\s*")
    if len(body) < 12:
        try:
            import pyperclip
            body = (pyperclip.paste() or "").strip()[:_MAX_IN]
        except Exception:
            body = ""
    if len(body) < 12:
        return ("Kya chhota karun, sir? Lamba text do ya kuch copy karke "
                "'tldr do' bolo.")
    out = _gen(f"Text: {body}",
               system=("Compress to ONE short sentence (a TL;DR) that keeps "
                       "the key point. Reply with just that sentence."),
               max_tokens=80)
    return out.strip() if out else _NO_MODEL


@skill(
    name="define_word",
    description="Give the meaning of a word/term using the local model (offline).",
    patterns=[
        "define karo word", "iska matlab batao", "ye shabd ka matlab",
        "word meaning batao", "matlab kya hai iska", "define karo",
        "is word ka arth batao",
    ],
    required_entities=[],
)
def define_word(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _strip(raw,
                  r".*?(?:define\s*karo|is\s*word\s*ka|iska|ye\s*shabd\s*ka|"
                  r"word|shabd)?\s*(?:ka)?\s*(?:matlab|meaning|arth)?\s*"
                  r"(?:batao|kya\s*hai|do)?\s*[:\-]?\s*")
    if len(body) < 2:
        return ("Kaunsa word define karun, sir? Jaise 'define karo "
                "serendipity'.")
    out = _gen(f"Word/term: {body}",
               system=("Give a clear 1-2 sentence meaning of the word or "
                       "term, with a tiny example if useful. Hinglish theek "
                       "hai."), max_tokens=120)
    return out.strip() if out else _NO_MODEL


_PC_CMD = {"iske", "is", "ke", "ki", "pros", "and", "aur", "cons", "fayde",
           "nuksan", "nuksaan", "khoobiyan", "kamiyan", "advantages",
           "disadvantages", "acche", "bure", "points", "batao", "do", "bata"}
# how_to: drop only the meta "step by step / tarika batao" framing — keep
# task-carrying words (kaise/banaye/karte), else "chai kaise banaye" loses
# its verb.
_HT_CMD = {"step", "by", "how", "to", "steps", "tarika", "batao",
           "me", "mein", "iska", "ka", "process", "bata"}


@skill(
    name="pros_cons",
    description="List the pros and cons of a topic/decision using the local model (offline).",
    patterns=[
        "pros and cons batao", "iske fayde nuksan batao",
        "ki khoobiyan kamiyan", "pros cons do",
        "advantages disadvantages batao", "iske fayde aur nuksan",
        "acche bure points batao",
    ],
    required_entities=[],
)
def pros_cons(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _drop_words(raw, _PC_CMD)
    if len(body) < 3:
        return ("Kis cheez ke pros-cons, sir? Jaise 'electric car ke fayde "
                "nuksan batao'.")
    out = _gen(f"Topic: {body}",
               system=("List 2-3 PROS and 2-3 CONS. Format:\nPros:\n- ...\n"
                       "Cons:\n- ...\nKeep each point one short line. "
                       "Hinglish theek hai."), max_tokens=300)
    return out.strip() if out else _NO_MODEL


@skill(
    name="how_to_steps",
    description="Give simple step-by-step instructions for a task using the local model (offline).",
    patterns=[
        "step by step batao kaise", "how to karo", "steps batao",
        "kaise karte hain step by step", "tarika batao step by step",
        "iska tarika batao", "kaise banate hain steps me",
    ],
    required_entities=[],
)
def how_to_steps(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _drop_words(raw, _HT_CMD)
    if len(body) < 3:
        return ("Kis kaam ka tarika, sir? Jaise 'step by step batao chai "
                "kaise banaye'.")
    out = _gen(f"Task: {body}",
               system=("Give clear numbered steps (1., 2., 3., …) to do the "
                       "task. Keep each step one short line. Max 7 steps. "
                       "Hinglish theek hai."), max_tokens=300)
    return out.strip() if out else _NO_MODEL


_POEM_CMD = {"shayari", "shaayari", "poem", "kavita", "sunao", "likho",
             "banao", "do", "ek", "pe", "par", "on", "about", "ke", "baare"}


@skill(
    name="write_poem",
    description="Write a short poem or shayari, optionally on a topic (offline local model).",
    patterns=[
        "shayari sunao", "ek poem likho", "shayari likho pyar pe",
        "poem banao nature pe", "kavita sunao", "shayari batao",
        "ek chhoti poem do", "dosti pe shayari",
    ],
    required_entities=[],
)
def write_poem(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    is_shayari = bool(re.search(r"shayari|shaayari|kavita", raw, re.I))
    topic = _drop_words(raw, _POEM_CMD)
    on = f" on {topic}" if topic else ""
    form = "a short 4-line Hinglish shayari" if is_shayari else "a short 4-6 line poem"
    out = _gen(f"Write {form}{on}.",
               system=("Write ONLY the poem/shayari, one line per line. "
                       "Keep it warm and simple. No preamble, no title."),
               max_tokens=160)
    return out.strip() if out else _NO_MODEL


@skill(
    name="motivate_me",
    description="A short motivational line/quote to lift the mood (offline local model).",
    patterns=[
        "motivate karo mujhe", "motivational quote do", "himmat badhao",
        "kuch motivational bolo", "mujhe motivate karo", "hausla badhao",
        "ek inspiring line do",
    ],
    required_entities=[],
)
def motivate_me(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    ctx = _drop_words(raw, {"motivate", "karo", "mujhe", "motivational",
                            "quote", "do", "himmat", "badhao", "kuch", "bolo",
                            "hausla", "ek", "inspiring", "line", "me"})
    about = f" for someone dealing with: {ctx}" if len(ctx) > 3 else ""
    out = _gen(f"Give ONE short, punchy motivational line{about}.",
               system=("Reply with just one warm, energising sentence in "
                       "Hinglish. No preamble, no quotes."), max_tokens=60)
    return out.strip().strip('"') if out else _NO_MODEL


@skill(
    name="tell_joke",
    description="A short clean joke to lighten the mood (offline local model).",
    patterns=[
        "ek joke sunao", "koi chutkula sunao", "joke batao",
        "kuch funny sunao", "hasao mujhe", "ek mazedaar joke do",
        "chutkula batao",
    ],
    required_entities=[],
)
def tell_joke(slots: dict) -> str:
    out = _gen("Tell one short, clean, family-friendly joke.",
               system=("Reply with just the joke (setup + punchline), 1-3 "
                       "lines, Hinglish theek hai. No preamble."),
               max_tokens=90)
    return out.strip() if out else _NO_MODEL


_STORY_CMD = {"kahani", "kahaani", "story", "sunao", "likho", "banao", "do",
              "ek", "chhoti", "choti", "short", "pe", "par", "on", "about",
              "ke", "baare", "wali", "me"}


@skill(
    name="tell_story",
    description="Tell a short story, optionally on a theme (offline local model).",
    patterns=[
        "kahani sunao", "ek chhoti story sunao", "story banao robot pe",
        "ek kahani likho", "bacho wali kahani sunao", "koi kahani do",
        "short story sunao", "ek kahani sunao raja pe",
    ],
    required_entities=[],
)
def tell_story(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    theme = _drop_words(raw, _STORY_CMD)
    on = f" about {theme}" if theme else ""
    out = _gen(f"Tell a short story{on} (5-8 sentences) with a small moral.",
               system=("Write a warm, simple short story with a beginning, "
                       "middle, and a gentle ending. Hinglish theek hai. "
                       "No title, no preamble."), max_tokens=320)
    return out.strip() if out else _NO_MODEL


@skill(
    name="tell_riddle",
    description="Ask a short riddle with its answer (offline local model).",
    patterns=[
        "riddle sunao", "ek paheli batao", "koi puzzle do", "riddle do",
        "paheli sunao", "ek riddle batao", "dimag ki paheli sunao",
    ],
    required_entities=[],
)
def tell_riddle(slots: dict) -> str:
    out = _gen("Give one short riddle and then its answer.",
               system=("Format:\nRiddle: <one or two lines>\nAnswer: <answer>\n"
                       "Keep it clever but solvable. Hinglish theek hai."),
               max_tokens=120)
    return out.strip() if out else _NO_MODEL


_SYN_CMD = {"synonym", "synonyms", "antonym", "antonyms", "opposite",
            "similar", "words", "word", "batao", "do", "iske", "is", "ke",
            "ka", "matlab", "wale", "same"}


@skill(
    name="synonyms_antonyms",
    description="Give synonyms (or antonyms) of a word using the local model (offline).",
    patterns=[
        "synonym batao", "iske synonyms do", "antonym batao",
        "opposite word batao", "similar words batao", "synonyms nikalo",
        "is word ke synonyms", "iska opposite kya hai",
    ],
    required_entities=[],
)
def synonyms_antonyms(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    want_ant = bool(re.search(r"antonym|opposite|ulta|vilom", raw, re.I))
    word = _drop_words(raw, _SYN_CMD)
    if len(word) < 2:
        return ("Kaunsa word, sir? Jaise 'happy ke synonyms batao'.")
    kind = "antonyms (opposite words)" if want_ant else "synonyms"
    out = _gen(f"Word: {word}\nGive 4-6 {kind}.",
               system=(f"Reply with just the {kind} as a comma-separated "
                       "list, nothing else."), max_tokens=60)
    return out.strip() if out else _NO_MODEL


@skill(
    name="rephrase_text",
    description="Rephrase a sentence in a different way using the local model (offline).",
    patterns=[
        "rephrase karo", "isko dobara likho differently",
        "alag tarike se likho", "ye line rephrase karo", "paraphrase karo",
        "dusre shabdon me likho", "isko alag tarah se bolo",
    ],
    required_entities=[],
)
def rephrase_text(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    body = _strip(raw,
                  r".*?(?:isko|is|ye)?\s*(?:line|text)?\s*"
                  r"(?:rephrase|paraphrase|dobara|alag\s*tarike\s*se|dusre\s*"
                  r"shabdon\s*me|alag\s*tarah\s*se)\s*"
                  r"(?:likho|karo|bolo)?\s*(?:differently)?\s*[:\-]?\s*")
    if len(body) < 3:
        return ("Kya rephrase karun, sir? Sentence do — jaise 'rephrase karo "
                "I am very tired today'.")
    out = _gen(f"Sentence: {body}",
               system=("Rephrase the sentence in a different way, keeping the "
                       "same meaning and language. Reply with just the "
                       "rephrased sentence."))
    return out.strip() if out else _NO_MODEL


@skill(
    name="fun_fact",
    description="Share a short surprising fun fact (offline local model).",
    patterns=[
        "fun fact batao", "koi interesting baat batao", "random fact do",
        "ek fun fact sunao", "kuch naya batao", "amazing fact batao",
        "koi gyaan ki baat",
    ],
    required_entities=[],
)
def fun_fact(slots: dict) -> str:
    raw = slots.get("raw_text") or slots.get("text") or ""
    topic = _drop_words(raw, {"fun", "fact", "batao", "koi", "interesting",
                              "baat", "random", "do", "ek", "sunao", "kuch",
                              "naya", "amazing", "gyaan", "ki", "ka", "pe",
                              "about"})
    on = f" about {topic}" if len(topic) > 2 else ""
    out = _gen(f"Share ONE short surprising fun fact{on}.",
               system=("Reply with just one interesting, true-sounding fact "
                       "in one or two lines. Hinglish theek hai."),
               max_tokens=70)
    return out.strip() if out else _NO_MODEL


@skill(
    name="give_compliment",
    description="A warm, genuine compliment to brighten the mood (offline local model).",
    patterns=[
        "compliment do", "tareef karo", "kuch achha bolo mere baare me",
        "mujhe compliment do", "ek achhi baat bolo", "meri tareef karo",
        "kuch nice bolo",
    ],
    required_entities=[],
)
def give_compliment(slots: dict) -> str:
    out = _gen("Give one warm, genuine compliment to the user.",
               system=("Reply with just one kind, uplifting sentence in "
                       "Hinglish. Address them warmly. No preamble."),
               max_tokens=50)
    return out.strip().strip('"') if out else _NO_MODEL
