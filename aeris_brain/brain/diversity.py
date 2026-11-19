"""Controlled variety for generated data — so the brain isn't biased toward one
kind of person, topic, register or language mix.

Findings this follows (2025): synthetic data is markedly less diverse than human
data; persona prompting helps, but mostly through the overall framing and
length control rather than fine detail (Kambhatla et al., arXiv 2505.17390);
using each persona only once keeps diversity high (PiKa, arXiv 2510.06670).

So every generated conversation gets a *grid cell*: a persona (used once), a
topic, a register, a code-mix level, a mood, a length budget and a turn count —
sampled from balanced pools. The audit (brain/audit.py) then measures the
result instead of trusting the sampler.
"""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass

# ── names: balanced across gender × region × community ────────────────────
# (name, gender, region, community). Used for personas, contacts, memory facts.
NAMES: list[tuple[str, str, str, str]] = [
    # North
    ("Aarav", "m", "north", "hindu"), ("Ananya", "f", "north", "hindu"), ("Rohit", "m", "north", "hindu"),
    ("Neha", "f", "north", "hindu"), ("Harpreet", "f", "north", "sikh"), ("Gurpreet", "m", "north", "sikh"),
    ("Simran", "f", "north", "sikh"), ("Jaspreet", "m", "north", "sikh"), ("Imran", "m", "north", "muslim"),
    ("Ayesha", "f", "north", "muslim"), ("Faizan", "m", "north", "muslim"), ("Zoya", "f", "north", "muslim"),
    # West
    ("Aditya", "m", "west", "hindu"), ("Sneha", "f", "west", "hindu"), ("Kunal", "m", "west", "hindu"),
    ("Pooja", "f", "west", "hindu"), ("Zubin", "m", "west", "parsi"), ("Perizaad", "f", "west", "parsi"),
    ("Hetal", "f", "west", "jain"), ("Parth", "m", "west", "jain"), ("Sameer", "m", "west", "muslim"),
    ("Rukhsar", "f", "west", "muslim"), ("Joel", "m", "west", "christian"), ("Ria", "f", "west", "christian"),
    # South
    ("Karthik", "m", "south", "hindu"), ("Divya", "f", "south", "hindu"), ("Arjun", "m", "south", "hindu"),
    ("Lakshmi", "f", "south", "hindu"), ("Mohammed", "m", "south", "muslim"), ("Safiya", "f", "south", "muslim"),
    ("Anil", "m", "south", "christian"), ("Merin", "f", "south", "christian"), ("Vignesh", "m", "south", "hindu"),
    ("Keerthana", "f", "south", "hindu"), ("Joseph", "m", "south", "christian"), ("Shabana", "f", "south", "muslim"),
    # East
    ("Sourav", "m", "east", "hindu"), ("Ritika", "f", "east", "hindu"), ("Arnab", "m", "east", "hindu"),
    ("Moumita", "f", "east", "hindu"), ("Sohail", "m", "east", "muslim"), ("Nusrat", "f", "east", "muslim"),
    ("Subhashree", "f", "east", "hindu"), ("Debashish", "m", "east", "hindu"),
    # North-east
    ("Lalremruati", "f", "northeast", "christian"), ("Tenzing", "m", "northeast", "buddhist"),
    ("Bidisha", "f", "northeast", "hindu"), ("Rinchen", "m", "northeast", "buddhist"),
    ("Akum", "m", "northeast", "christian"), ("Mary", "f", "northeast", "christian"),
    # Central
    ("Vivek", "m", "central", "hindu"), ("Shalini", "f", "central", "hindu"), ("Asif", "m", "central", "muslim"),
    ("Nazia", "f", "central", "muslim"), ("Rajesh", "m", "central", "hindu"), ("Kavita", "f", "central", "hindu"),
    # Gender-neutral / nicknames people really save contacts as
    ("Sam", "x", "any", "any"), ("Kiran", "x", "any", "any"), ("Jyoti", "x", "any", "any"), ("Noor", "x", "any", "any"),
]

RELATIONS = ["mummy", "papa", "maa", "bhaiya", "didi", "dadi", "nana", "chacha", "mausi", "boss", "office wale sir",
             "mom", "dad", "my sister", "my brother", "wife", "husband", "beta", "doctor sahab"]


def balanced_names(rng: random.Random, n: int) -> list[str]:
    """n names cycling evenly through gender × region (no group dominates)."""
    groups: dict[tuple[str, str], list[str]] = {}
    for name, g, region, _ in NAMES:
        groups.setdefault((g, region), []).append(name)
    keys = list(groups)
    rng.shuffle(keys)
    out = []
    for i in range(n):
        out.append(rng.choice(groups[keys[i % len(keys)]]))
    return out


# ── personas: each combination used once ──────────────────────────────────
AGES = ["teenager in school", "college student", "early-career professional", "working parent",
        "mid-career professional", "retired senior", "homemaker", "small business owner"]
CITIES = ["Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow",
          "Patna", "Bhopal", "Indore", "Chandigarh", "Kochi", "Guwahati", "Bhubaneswar", "Nagpur", "Surat", "Varanasi",
          "Ranchi", "Dehradun", "Coimbatore", "Visakhapatnam", "Raipur", "Shillong", "Kanpur", "Amritsar", "Mysuru",
          "a small town in UP", "a village in Bihar", "a town in Rajasthan", "a town in Maharashtra", "a town in MP"]
JOBS = ["software engineer", "teacher", "nurse", "shop owner", "delivery rider", "accountant", "student", "doctor",
        "driver", "farmer", "designer", "sales executive", "civil engineer", "government clerk", "chef", "electrician",
        "content creator", "bank employee", "lawyer", "security guard", "tailor", "pharmacist", "data analyst",
        "call-centre agent", "retired army officer", "beautician", "mechanic", "journalist"]
INTERESTS = ["cricket", "Bollywood", "cooking", "gym", "coding", "music", "travel", "gaming", "reading", "gardening",
             "photography", "stock market", "dance", "anime", "devotional music", "football", "fashion", "pets",
             "yoga", "street food", "web series", "astrology", "cars", "bikes", "poetry", "news", "badminton"]


def persona_stream(rng: random.Random):
    """Yields unique persona strings forever. Every age x city x job is used
    once per pass (even coverage); gender + interest pair make each string
    unique across passes (~5M combinations), so big runs never run dry."""
    space = list(itertools.product(range(len(AGES)), range(len(CITIES)), range(len(JOBS))))
    seen: set[str] = set()
    while True:
        rng.shuffle(space)
        for a, c, j in space:
            for _ in range(20):
                gender = rng.choice(["man", "woman"])  # the user's own gendered verbs vary too
                ints = rng.sample(INTERESTS, 2)
                p = f"a {AGES[a]} ({gender}), {JOBS[j]} from {CITIES[c]}, into {ints[0]} and {ints[1]}"
                if p not in seen:
                    seen.add(p)
                    yield p
                    break


# ── topics: what people actually chat with an assistant about ─────────────
# (topic, AERIS's expected response kind). "reply" = answer in chat;
# "escalate" = needs live/expert info → the brain must hand it off, not invent.
TOPICS: list[tuple[str, str]] = [
    ("greeting and how their day is going", "reply"), ("feeling bored, wants to chat", "reply"),
    ("stressed about exams", "reply"), ("tired after a long work day", "reply"),
    ("feeling lonely tonight", "reply"), ("excited about good news (got a job / passed)", "reply"),
    ("asking AERIS who it is and what it can do", "reply"), ("asking for a joke", "reply"),
    ("asking for a short motivational line", "reply"), ("what to cook for dinner with what's at home", "reply"),
    ("simple chai / recipe tips", "reply"), ("which movie or web series to watch tonight", "reply"),
    ("cricket chat — favourite players, a match they watched", "reply"), ("planning a weekend outing", "reply"),
    ("gift ideas for a family member's birthday", "reply"), ("how to sleep better", "reply"),
    ("how to focus while studying", "reply"), ("basic tips to save money each month", "reply"),
    ("how to start going to the gym", "reply"), ("learning a new skill (coding / guitar / English)", "reply"),
    ("a fight with a friend, wants advice", "reply"), ("nervous about a job interview", "reply"),
    ("festival plans (Diwali / Eid / Christmas / Pongal / Durga Puja)", "reply"),
    ("simple general-knowledge question with a well-known answer", "reply"),
    ("explain a simple concept (what is an API / how UPI works)", "reply"), ("riddle or word game", "reply"),
    ("compliments AERIS / thanks AERIS", "reply"), ("annoyed at AERIS for a mistake", "reply"),
    ("asking AERIS's opinion on something light (tea or coffee)", "reply"), ("pet care basics", "reply"),
    ("phone tips (battery saving, storage full)", "reply"), ("travel packing checklist", "reply"),
    ("today's weather / rain forecast", "escalate"), ("live cricket score", "escalate"),
    ("latest news headlines", "escalate"), ("current price of gold / petrol / a stock", "escalate"),
    ("a medical symptom that sounds serious", "escalate"), ("legal or tax advice for their situation", "escalate"),
    ("train / flight status", "escalate"), ("exact facts AERIS may not know (a niche date or statistic)", "escalate"),
]

REGISTERS = [
    "polite, uses 'aap'", "casual, uses 'tum'", "very casual with friends' slang ('yaar', 'bhai', 'tu')",
    "formal Indian English", "casual Indian English",
]
MIX_LEVELS = [
    ("english", "only English, no Hindi words"),
    ("en_heavy", "mostly English with a few Hindi words (yaar, accha, na)"),
    ("balanced", "a natural even mix of Hindi and English words"),
    ("hi_heavy", "mostly Hindi (in English letters) with a few English words"),
]
MOODS = ["cheerful", "neutral", "tired", "curious", "stressed", "playful", "sad", "irritated", "excited", "grateful"]
LENGTHS = ["very short messages (3-6 words)", "short messages (6-12 words)", "medium messages (10-20 words)"]


@dataclass
class Cell:
    persona: str
    topic: str
    expect: str        # reply | escalate
    register: str
    mix: str           # bucket id
    mix_desc: str
    mood: str
    length: str
    turns: int


def grid(rng: random.Random, n: int) -> list[Cell]:
    """n grid cells: topics/registers/mix levels/moods cycle evenly (balanced),
    personas never repeat, turn counts 1-4 favouring 2-3."""
    personas = persona_stream(rng)

    def even(pool, k):
        out = [pool[i % len(pool)] for i in range(k)]
        rng.shuffle(out)
        return out

    topics, regs, mixes = even(TOPICS, n), even(REGISTERS, n), even(MIX_LEVELS, n)
    moods, lengths = even(MOODS, n), even(LENGTHS, n)
    cells = []
    for i in range(n):
        (topic, expect), (mix, mix_desc) = topics[i], mixes[i]
        reg = regs[i]
        if mix == "english" and "English" not in reg:  # Hindi registers don't fit English-only cells
            reg = rng.choice(["formal Indian English", "casual Indian English"])
        cells.append(Cell(next(personas), topic, expect, reg, mix, mix_desc, moods[i], lengths[i],
                          rng.choices([1, 2, 3, 4], weights=[2, 4, 3, 1])[0]))
    return cells
