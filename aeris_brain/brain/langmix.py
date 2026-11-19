"""Language mix of a romanised Hinglish / English utterance.

Used three ways:
  * NLU labels      — `lang` for every user turn ("english" | "hinglish" | "hindi_roman" | "devanagari")
  * the audit       — code-mixing index (CMI) histogram, so the data covers the whole
                      English ↔ Hindi spectrum instead of piling up in one bucket
  * augmentation    — `spell_vary` adds the real spelling spread of typed Hinglish
                      (nahi / nahin / nhi) without ever touching a labelled span

Word-level language ID uses a lexicon of common romanised Hindi words; any other
alphabetic word counts as English. Words that are real in both languages ("main",
"to", "do", "hi") are language-independent and left out of the counts.

CMI follows Das & Gambäck (2014): 100 · (1 − max(lang count) / (tokens − independent)).
Stdlib only.
"""
from __future__ import annotations

import random
import re

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")

# Common romanised Hindi (function words, verbs, everyday nouns/adjectives, spelling variants).
HINDI = set("""
hai hain ho hoon hu hun tha thi the thhe hoga hogi honge kya kyaa kia kyun kyu kyon kaise kese kaisa kaisi kahan kaha kab
kaun kon kitna kitni kitne kidhar idhar udhar yahan wahan ab abhi abi kabhi phir fir aur ya lekin magar par pe ko ka ki ke
se mein mai mujhe mujhko tujhe tumhe tumko aapko hume humko unko usko isko inko iska uska unka mera meri mere tera teri tere
tumhara tumhari aapka aapki apna apni apne hamara hamari unki unke uski uske iski iske woh wo yeh ye voh yah koi kuch kuchh
sab sabhi bahut bohot bahot bhut zyada jyada kam thoda thodi bilkul sach jhooth haan han haa nahi nahin nhi naa mat
karo karna karne karke kar kiya kiye ki kari karta karti karte raha rahi rahe rahaa gaya gayi gaye gai jao jana jaana jaa
aa aao aana aaya aayi aaye aate aati dekh dekho dekhna dekha suno sun suna bolo bol bola boli batao bata batana bataya
chalo chal chala chalna lagao laga lagana do de dena diya diye dijiye lo le lena liya lijiye milo mil mila milna
sakta sakti sakte chahiye chahta chahti chahte pata samajh samjha samjho socho soch yaad rakho rakh rakhna kholo khol
band bandh chalu shuru khatam ruko ruk bas accha acha achha acchha theek thik sahi galat badhiya mast bekar bura buri
yaar yar bhai bhaiya didi behen dost ghar kaam paisa paise khana pani chai subah shaam sham raat din kal parso aaj
abhi jaldi der baad pehle saath bina liye wala wali wale waala waali agar toh to jab tab kyunki isliye shayad zaroor
bhi hi sirf bas aisa aise waisa waise kitne log ladka ladki baccha bache mummy papa maa beta beti dard thak neend
mujhse tumse aapse unse humse batayo pyaar dil mann khush udaas naraz gussa dar pareshan mazaa maza
""".split())

# Real words in both languages — not evidence for either.
AMBIGUOUS = set("main to do he me us hi is par pe the a i or so na ho bus die man mat sun ban hum".split())


def is_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI.search(text or ""))


def word_langs(text: str) -> list[tuple[str, str]]:
    """[(word, 'hi'|'en'|'x')] — 'x' = language-independent."""
    out = []
    for w in _WORD.findall(text or ""):
        lw = w.lower()
        out.append((w, "x" if lw in AMBIGUOUS else "hi" if lw in HINDI else "en"))
    return out


def cmi(text: str) -> float:
    """Code-mixing index 0 (monolingual) … 50 (perfectly balanced)."""
    tags = [t for _, t in word_langs(text)]
    n, u = len(tags), tags.count("x")
    if n - u <= 0:
        return 0.0
    return round(100 * (1 - max(tags.count("hi"), tags.count("en")) / (n - u)), 1)


def lang_label(text: str) -> str:
    """english | hinglish | hindi_roman | devanagari."""
    if is_devanagari(text):
        return "devanagari"
    tags = [t for _, t in word_langs(text) if t != "x"]
    if not tags:
        return "english"
    hi = tags.count("hi") / len(tags)
    if hi < 0.15:
        return "english"
    if hi > 0.85:
        return "hindi_roman"
    return "hinglish"


def mix_bucket(text: str) -> str:
    """Coarse spectrum bucket for balancing: en | en_heavy | balanced | hi_heavy | deva."""
    if is_devanagari(text):
        return "deva"
    tags = [t for _, t in word_langs(text) if t != "x"]
    if not tags:
        return "en"
    hi = tags.count("hi") / len(tags)
    return "en" if hi < 0.15 else "en_heavy" if hi < 0.4 else "balanced" if hi < 0.65 else "hi_heavy"


# ── spelling spread of typed Hinglish ──────────────────────────────────────
VARIANTS: dict[str, list[str]] = {
    "nahi": ["nahin", "nhi"], "kya": ["kyaa", "kia"], "kyun": ["kyu", "kyon"], "mein": ["me", "mai"],
    "accha": ["acha", "achha", "acchha"], "theek": ["thik", "thek"], "bahut": ["bohot", "bahot", "bhut"],
    "yaar": ["yar"], "kaise": ["kese", "kaisay"], "kuch": ["kuchh"], "haan": ["han", "haa"],
    "abhi": ["abi"], "please": ["plz", "pls"], "thanks": ["thnx", "thx"], "okay": ["ok", "okk"],
    "kaisa": ["kesa"], "hoon": ["hu", "hun"], "zyada": ["jyada"], "phir": ["fir"], "batao": ["btao"],
    "karo": ["kro"], "tum": ["tm"], "matlab": ["mtlb"], "pata": ["pta"], "sab": ["sb"],
}


def spell_vary(text: str, protected: list[str] = (), rate: float = 0.3,
               rng: random.Random | None = None) -> str:
    """Swap known words for common variants, never inside a protected span
    (names, numbers, message text — labels must stay exact)."""
    rng = rng or random.Random(0)
    spans = []
    low = text.lower()
    for p in protected:
        i = low.find(p.lower()) if p else -1
        if i >= 0:
            spans.append((i, i + len(p)))

    def inside(a: int, b: int) -> bool:
        return any(a < e and b > s for s, e in spans)

    def sub(m: re.Match) -> str:
        w = m.group(0)
        alts = VARIANTS.get(w.lower())
        if not alts or inside(m.start(), m.end()) or rng.random() > rate:
            return w
        alt = rng.choice(alts)
        return alt.capitalize() if w[:1].isupper() else alt

    return _WORD.sub(sub, text)
