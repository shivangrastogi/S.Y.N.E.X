"""Memory data without a teacher model (deterministic, exactly labelled).

Two kinds of records:

1. TURN with retrieved memory in the system prompt ("Things the user told you
   to remember: …", see prompt.py). The user asks; the target is a spoken
   reply that USES the right fact — with 1-3 distractor facts present — or,
   when the asked thing isn't in memory, an honest "aapne ye nahi bataya"
   (never invented). AERIS is male: "raha hoon", "sakta hoon".

2. MEMORY extraction (nlu.make_memory): a few user turns → the lasting facts,
   copied in the user's words; small talk and one-off commands → [].

Facts/questions come in English and Hinglish with balanced names
(diversity.balanced_names) and many fact categories, so recall isn't biased to
"parking" and "birthdays".

    py -m brain.memory_data --n 6000 --out out/memory
"""
from __future__ import annotations

import argparse
import json
import os
import random

from .diversity import balanced_names
from .langmix import spell_vary
from .nlu import make_memory

# category: (facts [hi, en], questions [hi, en]) — {x} slots filled from POOLS
CATS = {
    "car_parking": (["meri car {lvl} mein parked hai", "gaadi {lvl} mein lagayi hai"],
                    ["my car is parked at {lvl}", "I left the car at {lvl}"],
                    ["car kahan park ki thi?", "gaadi kahan khadi hai?", "car kidhar lagayi thi?"],
                    ["where did I park the car?", "where's my car?", "where did I leave the car?"]),
    "bike_parking": (["bike {lvl} ke paas khadi hai", "scooty {lvl} mein lagayi hai"],
                     ["I parked the bike near {lvl}", "the scooter is at {lvl}"],
                     ["bike kidhar lagayi thi?", "bike kahan khadi hai?"],
                     ["where is the bike parked?", "where did I leave my bike?"]),
    "wifi": (["wifi ka password {pw} hai"], ["the wifi password is {pw}"],
             ["wifi ka password kya hai?", "wifi password batao"], ["what's the wifi password?", "tell me the wifi password"]),
    "birthday": (["{name} ka birthday {date} ko hai"], ["{name}'s birthday is on {date}"],
                 ["{name} ka birthday kab hai?", "{name} ki birthday kab aati hai?"], ["when is {name}'s birthday?"]),
    "keys": (["chaabi {spot} mein rakhi hai"], ["the keys are in {spot}"],
             ["chaabi kahan rakhi thi?", "keys kidhar hain?"], ["where did I keep the keys?", "where are my keys?"]),
    "medicine": (["mujhe {med} {when} leni hai"], ["I take {med} {when}"],
                 ["dawai kab leni hai?", "{med} kab khaani hai?"], ["when do I take my medicine?", "when should I take {med}?"]),
    "food": (["mera favourite khana {food} hai"], ["my favourite food is {food}"],
             ["mera favourite khana kya hai?", "mujhe kya khana pasand hai?"], ["what's my favourite food?"]),
    "locker": (["locker ka code {code} hai"], ["the locker code is {code}"],
               ["locker ka code kya tha?", "locker code batao"], ["what was the locker code?"]),
    "appointment": (["{date} ko doctor ka appointment hai"], ["I have a doctor's appointment on {date}"],
                    ["doctor appointment kab hai?", "doctor ke paas kab jaana hai?"], ["when is my doctor appointment?"]),
    "blood": (["mera blood group {bg} hai"], ["my blood group is {bg}"],
              ["mera blood group kya hai?"], ["what's my blood group?"]),
    "vehicle": (["meri gaadi ka number {plate} hai"], ["my car number is {plate}"],
                ["gaadi ka number kya hai?"], ["what's my car number?"]),
    "pickup": (["bachchon ki school pickup {clock} baje hoti hai"], ["school pickup is at {clock}"],
               ["school pickup kitne baje hai?"], ["what time is school pickup?"]),
    "landlord": (["landlord ka naam {name} hai"], ["my landlord's name is {name}"],
                 ["landlord ka naam kya hai?"], ["what's my landlord's name?"]),
    "gym": (["main {days} ko gym jaata hoon", "main {days} ko gym jaati hoon"], ["I go to the gym on {days}"],
            ["main gym kab jaata hoon?", "gym kis din jaana hai?"], ["which days do I go to the gym?"]),
}
POOLS = {
    "lvl": ["B2", "basement level 1", "P3 pillar 14", "gate number 2", "mall ke parking", "office ke peeche",
            "level 4 slot 22", "the north lot", "Sector 18 market"],
    "pw": ["tiger123", "Sharma@2024", "home_net_99", "chaiwala7", "Monsoon#55", "qwerty789", "Blue-Door-12"],
    "date": ["12 March", "3 July", "25 December", "5 August", "18 October", "1 January", "29 February",
             "agle Monday", "kal", "next Friday"],
    "spot": ["drawer", "almirah ke upar wale khaane", "bag ki side pocket", "the blue box", "shoe rack",
             "kitchen ki shelf", "the car dashboard"],
    "med": ["BP ki goli", "vitamin D", "thyroid ki dawai", "insulin", "the iron tablet", "antibiotic"],
    "when": ["subah khaane ke baad", "raat ko sone se pehle", "har 8 ghante mein", "after breakfast", "at 9 pm"],
    "food": ["rajma chawal", "masala dosa", "biryani", "chole bhature", "momos", "fish curry", "poha", "paneer tikka"],
    "code": ["4512", "7781B", "0909", "2468", "1357", "8086"],
    "bg": ["B positive", "O negative", "A positive", "AB positive", "O positive"],
    "plate": ["DL 3C AB 1234", "MH 12 XY 9087", "KA 05 MN 4421", "UP 32 GT 7788", "TN 09 BX 3300"],
    "clock": ["2:30", "1:45", "3", "12:15"],
    "days": ["Monday Wednesday Friday", "weekends", "Tuesday aur Thursday", "every morning"],
}

ANSWER_HI = ["Aapne bataya tha, {fact}.", "Haan yaad hai, {fact}.", "Mere paas likha hai: {fact}.", "{fact}, aapne hi bataya tha."]
ANSWER_EN = ["You told me {fact}.", "I remember — {fact}.", "You mentioned that {fact}.", "According to what you told me, {fact}."]
UNKNOWN_HI = ["Aapne iske baare mein mujhe kuch nahi bataya. Bata do, main yaad rakh lunga.",
              "Ye mujhe nahi pata, aapne kabhi bataya nahi. Abhi bata do toh yaad rakh lunga."]
UNKNOWN_EN = ["You haven't told me that yet. Tell me and I'll remember it.",
              "I don't have that saved. Want me to remember it now?"]
# Things people say that are NOT lasting facts (moods, one-off plans, commands, opinions) —
# the memory head must learn to ignore these. Wide on purpose: the audit flagged a
# 10-line version as 73 % duplicates.
SMALLTALK = [
    "kaise ho?", "aaj bahut thak gaya yaar", "ek joke sunao", "torch on karo", "how's it going?", "play some music",
    "kal ka plan kuch nahi hai", "thanks yaar", "office mein boring din tha", "good night", "aaj mood off hai",
    "abhi khana kha raha hoon", "baarish ho rahi hai kya bahar?", "yaar neend aa rahi hai", "kya scene hai?",
    "aaj traffic bahut tha", "volume thoda kam karo", "match dekh rahe ho?", "chai peene ka mann hai",
    "what's up AERIS", "I'm so bored right now", "remind me in 10 minutes", "set an alarm for 6",
    "that movie was really good", "aaj gym nahi gaya", "kal shayad late uthunga", "phone ki battery kitni hai?",
    "I had a long day at work", "koi achha gaana bajao", "accha chalo bye", "haha that's funny",
    "kuch interesting batao", "aaj kaafi garmi hai", "I need a break", "tum bahut helpful ho",
    "maine abhi dinner order kiya", "lunch mein kya banau?", "aaj Sunday hai finally", "exam ki tension hai",
    "screen brightness badhao", "WhatsApp kholo", "aaj bahut kaam tha yaar", "hmm theek hai",
    "can you tell me a fun fact", "mujhe bhook lagi hai", "aaj kal kuch naya seekh raha hoon", "okay noted",
    "I just woke up", "the wifi is slow today", "kal milte hain", "wah kya baat hai", "I'm watching a series",
    "bas thoda aaram kar raha hoon", "aaj shopping gaya tha", "camera kholo", "what time is it?",
    "kya chal raha hai life mein", "I'm feeling much better today", "aaj ka din achha tha", "nahi abhi nahi",
]
Q_PRE_HI = ["", "", "", "AERIS, ", "suno, ", "yaar ", "ek baat batao, ", "hey ", "zara bataoge, "]
Q_SUF_HI = ["", "", "", " yaar", " please", " zara batao", " jaldi", " bhool gaya"]
Q_PRE_EN = ["", "", "", "hey, ", "quick question: ", "AERIS, ", "remind me, "]
Q_SUF_EN = ["", "", "", " please", " again?", " — I forgot"]


_SHIFT_HI = [(r"\bmeri\b", "aapki"), (r"\bmera\b", "aapka"), (r"\bmere\b", "aapke"), (r"\bmujhe\b", "aapko"),
             (r"\bmujhko\b", "aapko"), (r"\bmain\b", "aap"), (r"\b(jaata|jaati|leta|leti|karta|karti) hoon\b", None)]
_SHIFT_EN = [(r"\bI'm\b", "you're"), (r"\bmy\b", "your"), (r"\bMy\b", "Your"), (r"\bI\b", "you"), (r"\bme\b", "you")]
_VERB_HI = {"jaata": "jaate", "jaati": "jaate", "leta": "lete", "leti": "lete", "karta": "karte", "karti": "karte"}


def shift(fact: str, hi: bool) -> str:
    """User's words → how AERIS says them back: "meri car" → "aapki car",
    "main gym jaata hoon" → "aap gym jaate hain", "my car" → "your car"."""
    import re
    out = fact
    for pat, rep in (_SHIFT_HI if hi else _SHIFT_EN):
        if rep is None:
            out = re.sub(pat, lambda m: f"{_VERB_HI[m.group(1)]} hain", out)
        else:
            out = re.sub(pat, rep, out)
    return out


def _fill(tpl: str, rng: random.Random, name: str) -> str:
    out = tpl.replace("{name}", name)
    for k, v in POOLS.items():
        if "{" + k + "}" in out:
            out = out.replace("{" + k + "}", rng.choice(v))
    return out


def _fact(cat: str, hi: bool, rng: random.Random, name: str) -> tuple[str, str]:
    f_hi, f_en, q_hi, q_en = CATS[cat]
    tpl_f = rng.choice(f_hi if hi else f_en)
    fact = _fill(tpl_f, rng, name)
    q = _fill(rng.choice(q_hi if hi else q_en), rng, name)
    # natural openers/endings + typed spelling spread, so the same question
    # isn't asked the same way hundreds of times
    pre, suf = (Q_PRE_HI, Q_SUF_HI) if hi else (Q_PRE_EN, Q_SUF_EN)
    core = q.rstrip("?")
    q = f"{rng.choice(pre)}{core}{rng.choice(suf)}" + ("?" if q.endswith("?") else "")
    if hi:
        q = spell_vary(q, [], rate=0.3, rng=rng)
    return fact, q


def build(n: int, seed: int = 7, split: str = "train") -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    names = balanced_names(rng, n * 2)
    cats = list(CATS)
    turns, mems = [], []
    for i in range(n):
        hi = rng.random() < 0.6
        cat = cats[i % len(cats)]
        fact, q = _fact(cat, hi, rng, names[i])
        others = [c for c in cats if c != cat]
        distract = [_fact(c, hi, rng, names[-i - 1])[0] for c in rng.sample(others, rng.randint(1, 3))]
        known = rng.random() < 0.8  # 20% the asked fact is NOT in memory → honest "don't know"
        memory = distract + ([fact] if known else [])
        rng.shuffle(memory)
        if known:
            text = rng.choice(ANSWER_HI if hi else ANSWER_EN).format(fact=shift(fact, hi))
            text = text[0].upper() + text[1:]
        else:
            text = rng.choice(UNKNOWN_HI if hi else UNKNOWN_EN)
        turns.append({"split": split, "source": "memory_tpl", "family": "memory_qa", "lang": "hi" if hi else "en",
                      "prompt_lang": "match", "memory": memory, "now": None,
                      "messages": [{"role": "user", "content": q},
                                   {"role": "assistant", "content": {"type": "reply", "text": text}}],
                      "meta": {"category": cat, "known": known}, "id": f"mem-{split}-{i:07d}"})
        # extraction: the fact said naturally among 0-2 other turns (or none at all)
        if rng.random() < 0.75:
            lead = rng.choice(["yaad rakhna, ", "suno, ", "", "", "btw ", "note kar lo, "]) if hi else \
                rng.choice(["remember this: ", "fyi ", "", "", "just so you know, "])
            said = lead + fact
            user = [spell_vary(s, [], 0.3, rng) for s in rng.sample(SMALLTALK, rng.randint(0, 2))] + [said]
            rng.shuffle(user)
            mems.append(make_memory(user, [fact], source="memory_tpl", rid=f"memx-{split}-{i:07d}", split=split))
        else:
            mems.append(make_memory([spell_vary(s, [], 0.3, rng) for s in rng.sample(SMALLTALK, rng.randint(1, 3))],
                                    [], source="memory_tpl",
                                    rid=f"memx-{split}-{i:07d}", split=split))
    return turns, mems


def main(argv=None):
    ap = argparse.ArgumentParser(description="memory TURN + MEMORY-extraction records")
    ap.add_argument("--n", type=int, default=6000)
    ap.add_argument("--eval-n", type=int, default=400)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    for split, n, seed in (("train", a.n, 7), ("test", a.eval_n, 999)):
        t, m = build(n, seed, split)
        for name, rows in (("turn", t), ("extract", m)):
            p = os.path.join(a.out, f"{name}_{split}.jsonl")
            with open(p, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"{name}_{split}: {len(rows)} -> {p}")


if __name__ == "__main__":
    main()
