"""Non-single-call example families.

  ask        a required detail is missing → ask for it, then (multi-turn)
             complete the call from the user's answer
  pronoun    "call Ravi" … "also WhatsApp him I'm late" (context carries)
  multi      two actions in one sentence → two calls
  plan       work that needs the phone agent to operate apps
  escalate   knowledge / live info / no tool — incl. HARD NEGATIVES that
             mention a tool word ("what is WhatsApp?") but aren't commands
  reply      small talk the brain answers itself

Each builder returns (messages, meta) where messages alternate user /
assistant and every assistant content is a contract object (dict).
"""
from __future__ import annotations

import random

from . import slots as S
from .contract import make_call, validate
from .expand import Seg, Template, join, slot_values
from .augment import augment


# ── ask: incomplete requests ───────────────────────────────────────────────
# (tool, lang, template, missing-arg, ask texts en, ask texts hi)
INCOMPLETE = [
    ("send_message", "en", "(send a message|text|message) {contact}", "message",
     ["What should I tell {contact}?", "What's the message for {contact}?"],
     ["{contact} ko kya bolna hai?", "{contact} ko kya message bhejun?"]),
    ("send_message", "en", "send a whatsapp (message )?to {contact}", "message",
     ["What should the WhatsApp message to {contact} say?", "What do you want to send {contact}?"],
     ["{contact} ko WhatsApp pe kya bhejun?"]),
    ("send_message", "hi", "{contact} ko (message|whatsapp) (karo|bhejo|kar do)", "message",
     ["What should I tell {contact}?"], ["{contact} ko kya bolna hai?", "Kya message bhejun {contact} ko?"]),
    ("send_message", "en", "send a message saying {message}", "contact",
     ["Who should I send it to?", "Whom should I send that to?"], ["Kisko bhejun?", "Ye message kisko bhejna hai?"]),
    ("send_message", "hi", "message bhejo ki {message}", "contact",
     ["Who should I send it to?"], ["Kisko bhejun?", "Kisko bolna hai?"]),
    ("call", "en", "(make a call|call someone|i want to call)", "contact",
     ["Whom should I call?", "Who do you want to call?"], ["Kisko call karun?", "Kise phone lagaun?"]),
    ("call", "hi", "(call karo|phone lagao|ek call lagao)", "contact",
     ["Whom should I call?"], ["Kisko call karun?", "Kisko phone lagaun?"]),
    ("set_alarm", "en", "(set an alarm|wake me up|i need an alarm)", "time",
     ["For what time?", "What time should the alarm be?"], ["Kitne baje ka alarm lagaun?", "Kab ka alarm?"]),
    ("set_alarm", "hi", "(alarm laga do|alarm lagao|mujhe utha dena)", "time",
     ["For what time?"], ["Kitne baje ka alarm lagaun?", "Kitne baje uthana hai?"]),
    ("set_timer", "en", "(set|start) a timer", "duration",
     ["For how long?", "How long should the timer be?"], ["Kitne der ka timer?", "Kitne minute ka?"]),
    ("set_timer", "hi", "timer (laga do|lagao|chalu karo)", "duration",
     ["For how long?"], ["Kitne der ka timer lagaun?"]),
    ("open_app", "en", "open (the|an) app", "app",
     ["Which app should I open?"], ["Kaunsa app kholun?"]),
    ("play_music", "en", "play (that|the) song", "query",
     ["Which song should I play?"], ["Kaunsa gaana bajaun?"]),
    ("navigate_to", "en", "(give me directions|navigate|take me there)", "destination",
     ["Where do you want to go?"], ["Kahan jaana hai?"]),
    ("navigate_to", "hi", "(rasta batao|navigation chalu karo)", "destination",
     ["Where do you want to go?"], ["Kahan jaana hai?"]),
    ("set_reminder", "en", "(remind me|set a reminder)", "text",
     ["What should I remind you about?"], ["Kis cheez ka reminder lagaun?"]),
    ("translate", "en", "translate this", "text",
     ["What should I translate, and into which language?"], ["Kya translate karna hai, aur kis language mein?"]),
]

# how the user answers the question (multi-turn completion)
ANSWER = {
    "message": {"en": ["{message}", "tell (him|her|them) {message}", "say {message}", "{message} please"],
                "hi": ["{message}", "bolo ki {message}", "ye bhejo {message}"]},
    "contact": {"en": ["{contact}", "to {contact}", "send it to {contact}"],
                "hi": ["{contact}", "{contact} ko", "{contact} ko bhejo"]},
    "time": {"en": ["{time}", "at {time}", "make it {time}"], "hi": ["{time}", "{time} ka"]},
    "duration": {"en": ["{duration}", "for {duration}"], "hi": ["{duration}", "{duration} ka"]},
    "app": {"en": ["{app}", "open {app}"], "hi": ["{app}", "{app} kholo"]},
    "query": {"en": ["{music}", "play {music}"], "hi": ["{music}", "{music} bajao"]},
    "destination": {"en": ["{place}", "to {place}"], "hi": ["{place}", "{place} jaana hai"]},
    "text": {"en": ["to {remind}", "{remind}"], "hi": ["{remind}"]},
}
SLOT_OF_ARG = {"message": "message", "contact": "contact", "time": "time", "duration": "duration",
               "app": "app", "query": "music", "destination": "place", "text": "remind"}


def _lang_out(prompt_lang: str, user_lang: str) -> str:
    if prompt_lang == "english":
        return "en"
    if prompt_lang == "hinglish":
        return "hi"
    return user_lang


class Ctx:
    """Shared generation context: rng, split, a filler for slots."""

    def __init__(self, rng: random.Random, split: str, tools: dict):
        self.rng, self.split, self.tools = rng, split, tools

    def filler(self, lang: str, cache: dict | None = None):
        cache = {} if cache is None else cache
        rng, split = self.rng, self.split

        def fill(slot: str) -> str:
            if slot in cache:
                return cache[slot]
            v = _fill(slot, lang, rng, split)
            cache[slot] = v
            return v
        return fill


def _fill(slot: str, lang: str, rng: random.Random, split: str) -> str:
    L = lang if lang in ("en", "hi") else "en"
    simple = {
        "contact": S.CONTACTS, "app": S.APPS, "music": S.MUSIC, "search": S.SEARCH,
        "label": S.LABELS, "place": S.PLACES, "target": S.TAP_TARGETS,
        "text": S.TRANSLATE_TEXT, "lang_name": S.LANGUAGES, "title": S.EVENT_TITLES,
    }
    if slot in simple:
        return simple[slot].sample(rng, split)
    by_lang = {"message": S.MESSAGES, "time": S.TIMES, "days": S.DAYS,
               "duration": S.DURATIONS, "fact": S.FACTS, "recall": S.RECALL,
               "laptop_cmd": S.LAPTOP_CMDS, "note": S.NOTES, "remind": S.REMIND_TEXT}
    if slot in by_lang:
        # Hinglish sentences sometimes carry English values (code-mixing).
        src_lang = L if rng.random() < 0.8 else ("en" if L == "hi" else "hi")
        return by_lang[slot][src_lang].sample(rng, split)
    if slot == "number":
        return S.phone_number(rng, split)
    if slot == "expr":
        return S.maths(rng, L)
    if slot == "when":
        d = S.DAYS[L].sample(rng, split)
        t = S.TIMES[L].sample(rng, split)
        return rng.choice([f"{d} {t}" if L == "hi" else f"{d} at {t}", t, d])
    raise KeyError(f"no filler for slot {slot!r}")


def ask_example(ctx: Ctx, prompt_lang: str, multi_turn: bool):
    rng = ctx.rng
    tool, lang, src, missing, asks_en, asks_hi = rng.choice(INCOMPLETE)
    cache: dict = {}
    fill = ctx.filler(lang, cache)
    segs = Template(src).sample(rng, fill)
    user1 = join(augment(segs, rng, lang, 0.6))
    vals = slot_values(segs)
    out_lang = _lang_out(prompt_lang, lang)
    ask_t = rng.choice(asks_en if out_lang == "en" else asks_hi)
    ask_text = ask_t.format(contact=vals.get("contact", "them"))
    msgs = [{"role": "user", "content": user1},
            {"role": "assistant", "content": {"type": "ask", "text": ask_text, "pending": tool}}]
    if not multi_turn or missing not in ANSWER:
        return msgs, {"family": "ask", "tool": tool, "lang": lang}
    ans_src = rng.choice(ANSWER[missing][lang])
    aseg = Template(ans_src).sample(rng, fill)
    msgs.append({"role": "user", "content": join(augment(aseg, rng, lang, 0.4))})
    args = {}
    for slot, v in {**vals, **slot_values(aseg)}.items():
        arg = {"music": "query", "place": "destination", "remind": "text"}.get(slot, slot)
        if arg in ctx.tools[tool]["params"]:
            args[arg] = v
    if tool == "send_message" and "whatsapp" in user1.lower():
        args["app"] = "whatsapp"
    done = make_call(ctx.tools, (tool, args))
    if validate(done, ctx.tools):
        # the answer still leaves a required detail open (e.g. translate needs
        # text AND language) — keep just the clarifying question.
        return msgs[:2], {"family": "ask", "tool": tool, "lang": lang}
    msgs.append({"role": "assistant", "content": done})
    return msgs, {"family": "ask_complete", "tool": tool, "lang": lang}


# ── pronoun / context carry ────────────────────────────────────────────────
PRONOUN = {
    "en": [("call {contact}", "call", "(also |and )?(whatsapp|message|text) (him|her|them) (that |saying )?{message}"),
           ("whatsapp {contact} saying {message}", "send_message", "(now |also )?call (him|her|them)[ too]")],
    "hi": [("{contact} ko call karo", "call", "(aur |phir )?(use|unko) (whatsapp|message) (karo|bhejo) ki {message}"),
           ("{contact} ko whatsapp pe bolo {message}", "send_message", "(ab |phir )?(use|unko) call (karo|lagao)")],
}


def pronoun_example(ctx: Ctx, prompt_lang: str):
    rng = ctx.rng
    lang = rng.choice(["en", "hi"])
    first, tool1, second = rng.choice(PRONOUN[lang])
    cache: dict = {}
    fill = ctx.filler(lang, cache)
    s1 = Template(first).sample(rng, fill)
    v1 = slot_values(s1)
    args1 = {k: v for k, v in v1.items() if k in ctx.tools[tool1]["params"]}
    if tool1 == "send_message":
        args1["app"] = "whatsapp"
    msgs = [{"role": "user", "content": join(augment(s1, rng, lang, 0.4))},
            {"role": "assistant", "content": make_call(ctx.tools, (tool1, args1))}]
    s2 = Template(second).sample(rng, fill)
    v2 = slot_values(s2)
    u2 = join(augment(s2, rng, lang, 0.4))
    if tool1 == "call":
        args2 = {"contact": v1["contact"], "message": v2["message"]}
        if "whatsapp" in u2.lower():
            args2["app"] = "whatsapp"
        call2 = ("send_message", args2)
    else:
        call2 = ("call", {"contact": v1["contact"]})
    msgs += [{"role": "user", "content": u2},
             {"role": "assistant", "content": make_call(ctx.tools, call2)}]
    return msgs, {"family": "pronoun", "lang": lang}


# ── plans (phone agent) ────────────────────────────────────────────────────
AI_APPS = ["Gemini", "ChatGPT", "Copilot", "Meta AI"]
SUBJECTS = ["a person standing in a kitchen", "a cat wearing sunglasses", "a sunset over the sea",
            "a robot making chai", "a birthday cake with candles", "Mumbai in the rain",
            "a dragon flying over mountains", "a cozy reading corner", "a cartoon of a dog on a bike",
            "ek ladka cricket khelta hua", "Taj Mahal at night", "a futuristic city"]
PLANS = [
    ("en", "(generate|make|create) (an image|a picture|a photo) of {subject} (in|using|with) {ai} and send it to {contact} on whatsapp",
     ["Open {ai}", "Ask {ai} to generate an image of {subject}", "Wait for the image and download it",
      "Send the downloaded image to {contact} on WhatsApp"]),
    ("en", "(firstly|first) (generate|make) an image of {subject} and send it to {contact}",
     ["Open {ai}", "Ask {ai} to generate an image of {subject}", "Wait for the image and download it",
      "Send the downloaded image to {contact} on WhatsApp"]),
    ("hi", "{ai} se {subject} ki (image|photo|tasveer) banao aur {contact} ko whatsapp pe bhej do",
     ["Open {ai}", "Ask {ai} to generate an image of {subject}", "Wait for the image and download it",
      "Send the downloaded image to {contact} on WhatsApp"]),
    ("en", "open youtube(,| and) search (for )?{search} and play the first video",
     ["Open YouTube", "Search for {search}", "Tap the first video"]),
    ("hi", "youtube kholo(,| aur) {search} search karo (aur|phir) pehli video chalao",
     ["Open YouTube", "Search for {search}", "Tap the first video"]),
    ("en", "book (an uber|a cab|an ola) to {place}",
     ["Open the cab app", "Set the destination to {place}", "Show the fare and ask the user to confirm before booking"]),
    ("hi", "{place} ke liye (cab|uber|ola) book karo",
     ["Open the cab app", "Set the destination to {place}", "Show the fare and ask the user to confirm before booking"]),
    ("en", "(read|check) my (latest|last) email and (summarise|summarize) it",
     ["Open Gmail", "Open the most recent email", "Read the screen", "Summarise it for the user"]),
    ("en", "ask {ai} {question} and read me the answer",
     ["Open {ai}", "Type the question: {question}", "Wait for the answer", "Read the answer aloud"]),
    ("hi", "{ai} se pucho {question} aur jawab padh ke sunao",
     ["Open {ai}", "Type the question: {question}", "Wait for the answer", "Read the answer aloud"]),
    ("en", "order {food} from (swiggy|zomato)",
     ["Open the food app", "Search for {food}", "Add it to the cart", "Stop before payment and ask the user to confirm"]),
    ("hi", "(swiggy|zomato) se {food} order karo",
     ["Open the food app", "Search for {food}", "Add it to the cart", "Stop before payment and ask the user to confirm"]),
    ("en", "take a screenshot and send it to {contact} on whatsapp",
     ["Take a screenshot", "Send the screenshot to {contact} on WhatsApp"]),
    ("hi", "screenshot lo aur {contact} ko whatsapp pe bhej do",
     ["Take a screenshot", "Send the screenshot to {contact} on WhatsApp"]),
]
QUESTIONS = ["what to cook for dinner tonight", "a good name for a cafe", "how to fix a slow laptop",
             "ideas for mom's birthday", "aaj dinner mein kya banaun", "a 3 day Goa itinerary"]
FOODS = ["a paneer pizza", "biryani", "masala dosa", "two burgers", "chole bhature", "a coffee"]


def plan_example(ctx: Ctx):
    rng = ctx.rng
    lang, src, steps = rng.choice(PLANS)
    extra = {"subject": rng.choice(SUBJECTS), "ai": rng.choice(AI_APPS),
             "question": rng.choice(QUESTIONS), "food": rng.choice(FOODS)}
    fill0 = ctx.filler(lang)

    def fill(slot):
        return extra[slot] if slot in extra else fill0(slot)
    segs = Template(src).sample(rng, fill)
    vals = {**extra, **slot_values(segs)}
    user = join(augment(segs, rng, lang, 0.6))
    out = {"type": "plan", "goal": user,
           "steps": [s.format(**{k: vals.get(k, "") for k in
                                 ("ai", "subject", "contact", "search", "place", "question", "food")})
                     for s in steps]}
    return [{"role": "user", "content": user}, {"role": "assistant", "content": out}], \
        {"family": "plan", "lang": lang}


# ── multiple calls in one sentence ─────────────────────────────────────────
MULTI_OK = {"flashlight", "volume", "toggle_setting", "set_alarm", "set_timer", "open_app",
            "play_music", "battery_status", "date_time", "take_screenshot", "media_control",
            "brightness", "call"}
JOIN = {"en": [" and ", " and also ", ", then ", " and then ", ", also "],
        "hi": [" aur ", " aur phir ", ", phir ", " saath mein ", " uske baad "]}


def multi_example(ctx: Ctx, pick_single, prompt_lang: str):
    """pick_single(lang, allowed_tools) -> (segs, tool, args) from the
    template generator, so phrasing comes from the same split-aware pool."""
    rng = ctx.rng
    lang = rng.choice(["en", "hi"])
    a = pick_single(lang, MULTI_OK)
    b = pick_single(lang, MULTI_OK - {a[1]})
    text = join(a[0]) + rng.choice(JOIN[lang]) + join(b[0])
    out = make_call(ctx.tools, (a[1], a[2]), (b[1], b[2]))
    return [{"role": "user", "content": text}, {"role": "assistant", "content": out}], \
        {"family": "multi", "lang": lang, "tools": [a[1], b[1]]}


# ── escalate (incl. hard negatives) & small talk ───────────────────────────
ESCALATE = {
    "live_info": {
        "en": ["what's the weather today", "will it rain tomorrow", "what's the weather in {place}",
               "what is the cricket score", "who won the match yesterday", "latest news", "what's the news today",
               "what is the price of gold today", "how is the sensex doing", "is there traffic on the way to {place}",
               "what time does the metro close", "what's trending on twitter", "petrol price today",
               "what time is it in London", "when is the next train to {place}", "who is leading the election"],
        "hi": ["aaj mausam kaisa hai", "kal baarish hogi kya", "{place} ka weather kaisa hai", "score kya hua",
               "kal match kaun jeeta", "aaj ki news kya hai", "sone ka bhaav kya hai", "sensex kaisa chal raha hai",
               "{place} ke raste mein traffic hai kya", "petrol kitne ka hai aaj", "London mein kitne baje hain"]},
    "knowledge": {
        "en": ["who is the prime minister of india", "what is the capital of australia", "who invented the telephone",
               "what is whatsapp", "who invented the flashlight", "how does an alarm clock work",
               "what is a black hole", "explain photosynthesis", "who wrote the ramayana",
               "what is the speed of light", "why is the sky blue", "what does api stand for",
               "how many bones are in the human body", "what is youtube", "who founded spotify",
               "what is the difference between a virus and bacteria", "tell me about the mughal empire"],
        "hi": ["bharat ke pradhan mantri kaun hain", "whatsapp kya hai", "torch ka avishkar kisne kiya",
               "black hole kya hota hai", "photosynthesis samjhao", "ramayan kisne likhi",
               "aasmaan neela kyun hota hai", "insaan ke sharir mein kitni haddiyan hoti hain",
               "time travel possible hai kya", "alarm clock kaise kaam karti hai", "youtube kisne banaya"]},
    "complex": {
        "en": ["write me a 500 word essay on climate change", "plan a 7 day trip to europe with a budget",
               "help me prepare for a system design interview", "compare the iphone and pixel cameras in detail",
               "write a cover letter for a software job", "explain quantum computing in depth"],
        "hi": ["climate change pe 500 words ka essay likho", "europe ki 7 din ki trip plan karo budget ke saath",
               "system design interview ki taiyari karwao", "software job ke liye cover letter likho"]},
    "no_tool": {
        "en": ["order me a pizza and pay for it", "transfer 5000 rupees to Ravi", "book a flight to Goa and pay",
               "delete all my photos", "change my bank password", "hack my neighbour's wifi"],
        "hi": ["Ravi ko 5000 rupaye transfer karo", "saari photos delete kar do", "bank ka password badal do",
               "padosi ka wifi hack karo"]},
}
SMALLTALK = [
    (["hi", "hello", "hey", "hey aeris", "hello aeris"], ["hi", "hello", "namaste", "hello aeris"],
     ["Hi! What can I do for you?", "Hello! How can I help?"],
     ["Hello! Batao, kya karun?", "Namaste! Kya madad karun?"]),
    (["how are you", "how are you doing", "how's it going"], ["kaise ho", "kya haal hai", "kaisa hai aeris"],
     ["I'm doing great, thanks! How about you?", "All good here! What can I do for you?"],
     ["Main badhiya hoon! Tum batao?", "Ekdum mast! Kya madad karun?"]),
    (["thank you", "thanks", "thanks a lot", "great job"], ["thank you", "shukriya", "dhanyavaad", "bahut badhiya"],
     ["You're welcome!", "Happy to help!"], ["Koi baat nahi!", "Khushi hui madad karke!"]),
    (["who are you", "what's your name", "what can you do"], ["tum kaun ho", "tumhara naam kya hai", "tum kya kar sakte ho"],
     ["I'm AERIS, your phone assistant. I can call, message, set alarms, play music and much more.",
      "I'm AERIS! I can handle calls, messages, alarms, music and answer questions."],
     ["Main AERIS hoon, tumhara phone assistant. Call, message, alarm, music sab kar sakta hoon.",
      "Main AERIS hoon! Call, message, alarm, gaane — sab sambhal leta hoon."]),
    (["tell me a joke", "make me laugh", "say something funny"], ["ek joke sunao", "kuch funny bolo", "hasao mujhe"],
     ["Why did the phone wear glasses? It lost its contacts!", "I told my wifi a joke. It didn't get the connection."],
     ["Teacher: homework kahan hai? Student: sir, wifi ne kha liya!", "Mere phone ki battery bhi meri tarah hai, subah full, shaam tak khatam!"]),
    (["good morning", "morning aeris"], ["good morning", "suprabhat"],
     ["Good morning! Have a great day.", "Good morning! What's the plan today?"],
     ["Good morning! Din accha jaaye.", "Good morning! Aaj ka kya plan hai?"]),
    (["good night", "night aeris"], ["good night", "shubh ratri"],
     ["Good night! Sleep well.", "Good night, see you tomorrow!"], ["Good night! Achhe se sona.", "Shubh ratri! Kal milte hain."]),
    (["good evening"], ["good evening"],
     ["Good evening! How was your day?"], ["Good evening! Din kaisa raha?"]),
    (["i'm bored", "i am bored"], ["bore ho raha hoon", "main bore ho raha hoon"],
     ["Want me to play some music or tell you a joke?"], ["Gaana lagaun ya ek joke sunaun?"]),
    (["ok", "okay", "cool", "nice"], ["acha", "theek hai", "sahi hai", "badhiya"],
     ["Great!", "Cool, anything else?"], ["Badhiya!", "Theek hai, aur kuch?"]),
]


def escalate_example(ctx: Ctx):
    rng = ctx.rng
    reason = rng.choices(list(ESCALATE), weights=[4, 4, 2, 2])[0]
    lang = rng.choice(["en", "hi"])
    q = rng.choice(ESCALATE[reason][lang])
    if "{place}" in q:
        q = q.replace("{place}", S.PLACES.sample(rng, ctx.split))
    user = join(augment([Seg(q)], rng, lang, 0.5))
    return [{"role": "user", "content": user},
            {"role": "assistant", "content": {"type": "escalate", "reason": reason, "query": user}}], \
        {"family": "escalate", "reason": reason, "lang": lang}


def smalltalk_example(ctx: Ctx, prompt_lang: str):
    rng = ctx.rng
    en_in, hi_in, en_out, hi_out = rng.choice(SMALLTALK)
    lang = rng.choice(["en", "hi"])
    user = rng.choice(en_in if lang == "en" else hi_in)
    if rng.random() < 0.3:
        user = rng.choice(["aeris ", "hey aeris ", "jarvis "]) + user
    out_lang = _lang_out(prompt_lang, lang)
    text = rng.choice(en_out if out_lang == "en" else hi_out)
    return [{"role": "user", "content": user},
            {"role": "assistant", "content": {"type": "reply", "text": text}}], \
        {"family": "reply", "lang": lang}
