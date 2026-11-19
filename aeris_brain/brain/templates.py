"""Phrasing templates per tool, English ("en") and Hinglish ("hi").

Grammar (brain/expand.py): (a|b) choose, [x] optional, {slot} value.
A slot fills the tool arg of the same name unless ARG_OF says otherwise.
`const` holds normalised enum args the phrasing implies.

Each template is assigned to train/dev/test by a hash of its text
(see generate.split_of), so test sentences use phrasings the model never
saw — the honest measure of "understands commands", not "memorised them".
"""
from __future__ import annotations

from dataclasses import dataclass, field

# slot name → tool arg name, where they differ
ARG_OF = {
    "place": "destination", "expr": "expression", "laptop_cmd": "command",
    "remind": "text", "note": "text", "recall": "query", "lang_name": "target_language",
    "music": "query", "search": "query",
}
# per-tool overrides (send_email reuses the messaging slots)
ARG_OF_TOOL = {"send_email": {"contact": "to", "message": "body"}}


def arg_for(tool: str, slot: str) -> str:
    return ARG_OF_TOOL.get(tool, {}).get(slot) or ARG_OF.get(slot, slot)


@dataclass
class T:
    tool: str
    lang: str          # "en" | "hi"
    src: str
    const: dict = field(default_factory=dict)


def _many(tool, lang, const, *srcs):
    return [T(tool, lang, s, dict(const)) for s in srcs]


TEMPLATES: list[T] = []
add = TEMPLATES.extend

# ── flashlight ─────────────────────────────────────────────────────────────
add(_many("flashlight", "en", {"state": "on"},
    "(turn|switch) on the (flashlight|torch|flash light)",
    "(turn|switch) the (flashlight|torch) on",
    "(flashlight|torch) on",
    "i need (the torch|the flashlight|some light)",
    "(light up|put on) the (torch|flashlight)",
    "can you (turn|switch) on (the|my) (flashlight|torch)",
    "it's (too dark|dark here)[,] (turn on|switch on) the (torch|flashlight)",
    "enable (the|my) (flashlight|torch)"))
add(_many("flashlight", "en", {"state": "off"},
    "(turn|switch) off the (flashlight|torch)",
    "(turn|switch) the (flashlight|torch) off",
    "(flashlight|torch) off",
    "(kill|disable) the (flashlight|torch)",
    "(stop|shut off) the (torch|flashlight)",
    "i don't need the (torch|flashlight) (anymore|now)"))
add(_many("flashlight", "hi", {"state": "on"},
    "torch (on|chalu|jala) (karo|kar do|do)",
    "(flashlight|torch) (on|chalu) kar (do|de|dena)",
    "(andhera hai|bahut andhera hai)[,] torch (jalao|on karo)",
    "(roshni|light) (chahiye|karo)[,] torch on (karo|kar do)",
    "zara torch (jala|on kar) (do|dena)",
    "phone ki (torch|flashlight) (on|chalu) karo"))
add(_many("flashlight", "hi", {"state": "off"},
    "torch (band|off|bujha) (karo|kar do|do)",
    "(flashlight|torch) (band|off) kar (do|de|dena)",
    "torch (bujhao|bujha do)",
    "zara torch band kar (do|dena)",
    "ab torch ki zarurat nahi[,] band (karo|kar do)"))

# ── volume ─────────────────────────────────────────────────────────────────
add(_many("volume", "en", {"action": "up"},
    "(turn|crank) (up|it up)[ the] volume", "volume up", "(increase|raise) the volume",
    "(make it|it's too) (louder|quiet)", "louder[ please]", "i can't hear[ it][,] (turn it up|increase the volume)"))
add(_many("volume", "en", {"action": "down"},
    "(turn|bring) down the volume", "volume down", "(decrease|lower|reduce) the volume",
    "(it's too loud|too loud)[,] (turn it down|lower it)", "(quieter|softer)[ please]"))
add(_many("volume", "en", {"action": "mute"},
    "mute[ the] (phone|volume|sound|audio)", "(silence|mute) (it|everything)", "no sound[ please]"))
add(_many("volume", "en", {"action": "unmute"},
    "unmute[ the] (phone|sound|volume)", "turn the sound back on"))
add(_many("volume", "en", {"action": "max"},
    "(max|full) volume", "volume (to the max|full)", "turn the volume all the way up"))
add(_many("volume", "hi", {"action": "up"},
    "(volume|awaaz|aawaz) (badhao|badha do|tez karo|zyada karo)",
    "(awaaz|volume) thoda (badhao|tez karo)", "sunai nahi de raha[,] (volume|awaaz) badhao",
    "aur (tez|zor se)[ karo]"))
add(_many("volume", "hi", {"action": "down"},
    "(volume|awaaz|aawaz) (kam karo|kam kar do|ghatao|dheere karo)",
    "(bahut tez hai|bahut loud hai)[,] (awaaz|volume) kam karo", "thoda dheere[ karo]"))
add(_many("volume", "hi", {"action": "mute"},
    "(phone|volume|awaaz) (mute|silent) (karo|kar do)", "awaaz band (karo|kar do)"))
add(_many("volume", "hi", {"action": "max"},
    "volume (full|poora) (karo|kar do)", "(awaaz|volume) full (karo|pe kar do)"))

# ── brightness ─────────────────────────────────────────────────────────────
add(_many("brightness", "en", {"action": "up"},
    "(increase|raise|turn up) the brightness", "(make the screen|screen) brighter", "brightness up"))
add(_many("brightness", "en", {"action": "down"},
    "(decrease|lower|reduce|turn down) the brightness", "(dim the screen|screen is too bright)", "brightness down"))
add(_many("brightness", "en", {"action": "auto"},
    "(turn on|enable|set) (auto|adaptive) brightness"))
add(_many("brightness", "hi", {"action": "up"},
    "brightness (badhao|badha do|tez karo)", "screen (thodi|zyada) bright karo"))
add(_many("brightness", "hi", {"action": "down"},
    "brightness (kam karo|kam kar do|ghatao)", "screen (dim|thodi dark) karo", "aankhon mein chubh raha hai[,] brightness kam karo"))

# ── toggle_setting ─────────────────────────────────────────────────────────
for setting, en_names, hi_names in [
        ("wifi", ["wifi", "wi-fi", "the wifi"], ["wifi", "wi-fi"]),
        ("bluetooth", ["bluetooth", "the bluetooth"], ["bluetooth"]),
        ("airplane_mode", ["airplane mode", "flight mode", "aeroplane mode"], ["airplane mode", "flight mode"]),
        ("location", ["location", "gps", "location services"], ["location", "gps"]),
        ("hotspot", ["hotspot", "the hotspot", "mobile hotspot"], ["hotspot"]),
        ("dnd", ["do not disturb", "dnd"], ["dnd", "do not disturb"]),
        ("mobile_data", ["mobile data", "data", "internet"], ["mobile data", "data", "internet"]),
        ("auto_rotate", ["auto rotate", "screen rotation"], ["auto rotate"]),
        ("battery_saver", ["battery saver", "power saving mode"], ["battery saver"])]:
    en = "|".join(en_names)
    hi = "|".join(hi_names)
    add(_many("toggle_setting", "en", {"setting": setting, "state": "on"},
        f"(turn|switch) on ({en})", f"(enable|activate) ({en})", f"({en}) on[ please]",
        f"can you (turn|switch) on ({en})"))
    add(_many("toggle_setting", "en", {"setting": setting, "state": "off"},
        f"(turn|switch) off ({en})", f"(disable|deactivate) ({en})", f"({en}) off[ please]"))
    add(_many("toggle_setting", "hi", {"setting": setting, "state": "on"},
        f"({hi}) (on|chalu) (karo|kar do)", f"zara ({hi}) on kar (do|dena)"))
    add(_many("toggle_setting", "hi", {"setting": setting, "state": "off"},
        f"({hi}) (off|band) (karo|kar do)", f"({hi}) band kar (do|dena)"))

# ── open_settings ──────────────────────────────────────────────────────────
for page, en_names, hi_names in [
        ("main", ["settings", "the settings"], ["settings"]),
        ("wifi", ["wifi settings", "wi-fi settings"], ["wifi settings"]),
        ("bluetooth", ["bluetooth settings"], ["bluetooth settings"]),
        ("display", ["display settings", "screen settings"], ["display settings"]),
        ("sound", ["sound settings", "ringtone settings"], ["sound settings", "ringtone settings"]),
        ("battery", ["battery settings", "battery usage"], ["battery settings"]),
        ("apps", ["app settings", "installed apps"], ["app settings"]),
        ("storage", ["storage settings", "storage"], ["storage settings", "storage"]),
        ("notifications", ["notification settings"], ["notification settings"]),
        ("language", ["language settings"], ["language settings"]),
        ("about", ["about phone"], ["about phone"])]:
    en = "|".join(en_names)
    hi = "|".join(hi_names)
    add(_many("open_settings", "en", {"page": page},
        f"(open|show|go to) ({en})", f"take me to ({en})", f"i want to see ({en})"))
    add(_many("open_settings", "hi", {"page": page},
        f"({hi}) (kholo|khol do|dikhao)", f"({hi}) pe le chalo"))

# ── battery / date_time / calculate ────────────────────────────────────────
add(_many("battery_status", "en", {},
    "how much battery is left", "what's the battery (level|percentage)", "battery (percentage|level|status)",
    "how much charge (is left|do i have)", "is (the|my) phone charging", "check (the|my) battery"))
add(_many("battery_status", "hi", {},
    "battery kitni (hai|bachi hai)", "kitni battery (hai|bachi hai)", "charge kitna hai",
    "phone charge ho raha hai kya", "battery check karo"))
add(_many("date_time", "en", {"what": "time"},
    "what time is it[ now]", "what's the time", "(tell me|say) the time", "time please",
    "current time", "do you know what time it is"))
add(_many("date_time", "en", {"what": "date"},
    "what's the date[ today]", "what is today's date", "(tell me|what is) the date", "today's date[ please]"))
add(_many("date_time", "en", {"what": "day"},
    "what day is (it|today)", "which day is it[ today]", "is today (Monday|Friday|Sunday)"))
add(_many("date_time", "hi", {"what": "time"},
    "(kitne|kya) baje hain", "(time|samay) kya (hua|hai)", "abhi kitne baje hain", "time batao[ zara]", "kya time ho gaya"))
add(_many("date_time", "hi", {"what": "date"},
    "aaj (ki date|kya tareekh) (kya hai|hai)", "aaj kaunsi (date|tareekh) hai", "date batao"))
add(_many("date_time", "hi", {"what": "day"},
    "aaj (kaunsa|konsa) din hai", "aaj kya din hai", "aaj (somvar|sunday|friday) hai kya"))
add(_many("calculate", "en", {},
    "what is {expr}", "(calculate|compute|work out) {expr}", "how much is {expr}",
    "{expr}", "quick maths[,] {expr}", "can you calculate {expr}"))
add(_many("calculate", "hi", {},
    "{expr} kitna (hota hai|hai)", "{expr} (calculate karo|batao)", "zara {expr} karke batao",
    "{expr} kya aayega"))

# ── alarm / timer / reminder / calendar ────────────────────────────────────
add(_many("set_alarm", "en", {},
    "(set|put|make) an alarm (for|at) {time}", "wake me up at {time}",
    "(set|put) an alarm (for|at) {time} {days}", "{days}[,] wake me (up )?at {time}",
    "alarm (for|at) {time}", "i need an alarm (for|at) {time}",
    "(set|create) a {label} alarm (for|at) {time}", "remind me with an alarm at {time}",
    "can you set an alarm (for|at) {time}[ please]", "get me up at {time} {days}"))
add(_many("set_alarm", "hi", {},
    "{time} ka alarm (laga do|lagao|set karo)", "{time} (utha dena|jaga dena)",
    "{days} {time} ka alarm (lagao|laga do)", "{days} {time} utha dena",
    "alarm {time} (ka|pe) (laga do|set kar do)", "mujhe {time} (uthana|jagana) hai[,] alarm (laga do|lagao)",
    "{label} ke liye {time} ka alarm (lagao|laga do)", "{time} pe alarm (set karo|laga dena)"))
add(_many("set_timer", "en", {},
    "(set|start|put) a timer (for|of) {duration}", "timer (for|of) {duration}",
    "{duration} timer", "count down {duration}", "(set|start) a {duration} timer",
    "(set|start) a timer for {duration} for (the )?{label}", "remind me in {duration}",
    "start a {label} timer for {duration}"))
add(_many("set_timer", "hi", {},
    "{duration} ka timer (laga do|lagao|set karo|chalu karo)", "timer {duration} ka (laga do|lagao)",
    "{duration} baad (bata dena|yaad dila dena)", "{label} ke liye {duration} ka timer (lagao|laga do)",
    "{duration} ka countdown (shuru karo|chalao)"))
add(_many("set_reminder", "en", {},
    "remind me to {remind} {when}", "{when}[,] remind me to {remind}",
    "set a reminder to {remind} {when}", "remind me to {remind}",
    "don't let me forget to {remind} {when}", "add a reminder[:] {remind} {when}"))
add(_many("set_reminder", "hi", {},
    "{when} {remind} yaad dila dena", "mujhe {when} {remind} yaad (dilana|dila dena)",
    "{remind} ka reminder (lagao|laga do) {when}", "{remind} yaad dila dena",
    "reminder (lagao|set karo)[:] {remind} {when}"))
add(_many("create_calendar_event", "en", {},
    "(add|put|schedule) (a|an) {title} (on|for) {when}", "(add|create) a calendar event[:] {title} {when}",
    "schedule {title} {when}", "put {title} on my calendar (for|on) {when}"))
add(_many("create_calendar_event", "hi", {},
    "{when} {title} calendar mein (daal do|add karo)", "{title} ka event (bana do|add karo) {when}",
    "calendar mein {title} {when} (daalo|add kar do)"))

# ── call ───────────────────────────────────────────────────────────────────
add(_many("call", "en", {},
    "call {contact}", "(give|make) {contact} a call", "(phone|ring|dial) {contact}",
    "(make|place) a call to {contact}", "can you call {contact}[ please]",
    "get {contact} on the phone", "i want to (talk to|speak to|call) {contact}",
    "call {number}", "dial {number}", "(call|ring) this number {number}",
    "make a call to {number}"))
add(_many("call", "en", {"app": "whatsapp"},
    "whatsapp call {contact}", "(make|do) a whatsapp call to {contact}",
    "call {contact} on whatsapp", "(give|make) {contact} a whatsapp call"))
add(_many("call", "en", {"app": "whatsapp", "video": True},
    "(make a|start a) whatsapp video call (to|with) {contact}", "video call {contact} on whatsapp"))
add(_many("call", "en", {"video": True},
    "video call {contact}", "(start|make) a video call (to|with) {contact}"))
add(_many("call", "hi", {},
    "{contact} ko (call|phone) (karo|kar do|lagao|laga do|milao)",
    "{contact} ko phone (lagao|laga do|milao)", "{contact} se baat (karao|karni hai)",
    "zara {contact} ko call (karo|lagao)", "{contact} ka number (milao|dial karo)",
    "{number} pe call (karo|lagao)", "{number} (milao|dial karo)", "is number pe call karo {number}"))
add(_many("call", "hi", {"app": "whatsapp"},
    "{contact} ko whatsapp (call|pe call) (karo|lagao)", "whatsapp pe {contact} ko call (karo|lagao)"))
add(_many("call", "hi", {"video": True},
    "{contact} ko video call (karo|lagao)", "{contact} se video call pe baat (karao|karni hai)"))
add(_many("call", "hi", {"app": "whatsapp", "video": True},
    "{contact} ko whatsapp video call (karo|lagao)"))

# ── send_message ───────────────────────────────────────────────────────────
add(_many("send_message", "en", {"app": "whatsapp"},
    "send {contact} a whatsapp (message )?saying {message}",
    "send a whatsapp (message )?to {contact} saying {message}",
    "whatsapp {contact} (that|saying) {message}",
    "message {contact} on whatsapp (that|saying) {message}",
    "tell {contact} on whatsapp (that )?{message}",
    "send a whatsapp message on (this|the) number {number} {message}",
    "whatsapp {number} saying {message}",
    "(text|message) {number} on whatsapp (saying|that) {message}",
    "i want to send a whatsapp message to {contact} (saying|that) {message}"))
add(_many("send_message", "en", {"app": "sms"},
    "(send|text) {contact} an sms (saying|that) {message}",
    "send an (sms|text message) to {contact} saying {message}",
    "sms {number} (saying|that) {message}"))
add(_many("send_message", "en", {},
    "(text|message) {contact} (that|saying) {message}",
    "send (a message|a text) to {contact} (saying|that) {message}",
    "tell {contact} (that )?{message}", "let {contact} know (that )?{message}",
    "(message|text) {number} (saying|that) {message}",
    "can you (message|text) {contact} {message}"))
add(_many("send_message", "hi", {"app": "whatsapp"},
    "{contact} ko whatsapp (pe|par) (bolo|bol do|message karo|bhejo) (ki )?{message}",
    "whatsapp pe {contact} ko (bhejo|bol do|message karo) (ki )?{message}",
    "{contact} ko whatsapp karo ki {message}",
    "{number} pe whatsapp (karo|bhejo) {message}",
    "is number {number} pe whatsapp (pe )?{message} bhej do",
    "{contact} ko whatsapp pe {message} (likh do|bhej do)"))
add(_many("send_message", "hi", {"app": "sms"},
    "{contact} ko (sms|message) (bhejo|kar do) (ki )?{message}",
    "{number} pe sms (bhejo|karo) {message}"))
add(_many("send_message", "hi", {},
    "{contact} ko (bolo|bol do|keh do|bata do) (ki )?{message}",
    "{contact} ko message (karo|bhejo|kar do) (ki )?{message}",
    "{contact} ko {message} (bhej do|likh do|bol do)",
    "{number} pe message (karo|bhejo) {message}"))

# ── open_chat ──────────────────────────────────────────────────────────────
add(_many("open_chat", "en", {"app": "whatsapp"},
    "open {contact}'s (whatsapp )?chat", "open (my )?whatsapp chat with {contact}",
    "go to {contact}'s chat on whatsapp", "show me my chat with {contact} on whatsapp"))
add(_many("open_chat", "hi", {"app": "whatsapp"},
    "{contact} ki (whatsapp )?chat kholo", "whatsapp pe {contact} ki chat (kholo|khol do)",
    "{contact} wali chat (kholo|dikhao)"))

# ── send_email ─────────────────────────────────────────────────────────────
add(_many("send_email", "en", {},
    "(send|write) an email to {contact} saying {message}", "email {contact} (that|saying) {message}",
    "(send|write) a mail to {contact}"))
add(_many("send_email", "hi", {},
    "{contact} ko email (bhejo|karo) ki {message}", "{contact} ko mail (likho|bhejo)"))

# ── open_app ───────────────────────────────────────────────────────────────
add(_many("open_app", "en", {},
    "open {app}", "(launch|start) {app}", "(open|launch) the {app} app", "go to {app}",
    "take me to {app}", "can you open {app}[ for me]", "i want to use {app}",
    "(bring up|pull up) {app}", "{app} (please|now)"))
add(_many("open_app", "hi", {},
    "{app} (kholo|khol do|open karo|chalao|chalu karo)", "zara {app} (kholo|khol do)",
    "{app} (app )?open kar (do|dena)", "mujhe {app} (kholna|chalana) hai", "{app} pe le chalo"))

# ── web_search ─────────────────────────────────────────────────────────────
add(_many("web_search", "en", {"engine": "google"},
    "(search|google|look up) {search}", "search (for )?{search} on google",
    "google {search} for me", "find {search} (on the internet|online)", "(do a )?google search (for )?{search}"))
add(_many("web_search", "en", {"engine": "youtube"},
    "search (for )?{search} on youtube", "(find|look up) {search} on youtube",
    "youtube search {search}", "show me {search} (videos )?on youtube"))
add(_many("web_search", "hi", {"engine": "google"},
    "google pe {search} (search karo|dhundo|khojo)", "{search} (google karo|search karo)",
    "internet pe {search} (dhundo|search karo)", "{search} ke baare mein google (karo|pe dekho)"))
add(_many("web_search", "hi", {"engine": "youtube"},
    "youtube pe {search} (search karo|dhundo|lagao)", "{search} youtube pe (dhundo|dikhao)",
    "youtube par {search} ki video (lagao|dikhao)"))

# ── play_music / media_control ─────────────────────────────────────────────
add(_many("play_music", "en", {},
    "play {music}", "(play|put on) some {music}", "i want to (listen to|hear) {music}",
    "can you play {music}", "start playing {music}", "play (the song )?{music}[ please]"))
add(_many("play_music", "en", {"app": "spotify"},
    "play {music} on spotify", "(open spotify and play|spotify play) {music}"))
add(_many("play_music", "en", {"app": "youtube"},
    "play {music} on youtube", "put {music} on youtube"))
add(_many("play_music", "en", {},
    "play (some )?music", "put on some songs", "(i want|let's have) some music"))
add(_many("play_music", "hi", {},
    "{music} (bajao|chalao|lagao|suna do|play karo)", "{music} ke gaane (bajao|chalao|lagao)",
    "mujhe {music} sunna hai", "zara {music} (lagao|chala do)", "{music} wala gaana (bajao|chalao)"))
add(_many("play_music", "hi", {"app": "spotify"},
    "spotify pe {music} (chalao|bajao|lagao)"))
add(_many("play_music", "hi", {"app": "youtube"},
    "youtube pe {music} (chalao|bajao|lagao)"))
add(_many("play_music", "hi", {},
    "(gaana|gaane|music) (bajao|chalao|lagao)", "koi (gaana|song) (bajao|laga do)"))
for action, en, hi in [
        ("pause", ["pause[ the] (music|song|video)", "pause (it|this)", "hold the music"],
                  ["(gaana|music|video) (pause karo|rok do|rok)", "ruk ja gaana", "pause kar do"]),
        ("play", ["resume[ the] (music|song)", "(continue|keep) playing", "play it again"],
                 ["(gaana|music) (resume karo|phir se chalao|chalu karo)", "wapas chalao"]),
        ("next", ["(next|skip) (song|track)", "skip (this|this song)", "play the next (one|song)"],
                 ["agla (gaana|song)[ (lagao|chalao)]", "ye gaana (skip karo|badlo)", "next (gaana|song) lagao"]),
        ("previous", ["previous (song|track)", "go back (a song|to the last song)", "play the last song again"],
                     ["pichla (gaana|song)[ (lagao|chalao)]", "pehle wala gaana (lagao|chalao)"]),
        ("stop", ["stop the (music|song)", "stop playing"],
                 ["(gaana|music) band (karo|kar do)", "music (rok do|band karo)"])]:
    add(_many("media_control", "en", {"action": action}, *en))
    add(_many("media_control", "hi", {"action": action}, *hi))

# ── screen tools ───────────────────────────────────────────────────────────
add(_many("take_screenshot", "en", {},
    "take a screenshot", "(screenshot|capture) (this|the screen)", "grab a screenshot", "screenshot please"))
add(_many("take_screenshot", "hi", {},
    "screenshot (lo|le lo|le)", "is screen ka screenshot (lo|le lo)", "ss (lo|le lo)"))
for action, en, hi in [
        ("back", ["go back", "back", "previous screen"], ["(back|wapas|peeche) (jao|chalo)", "wapas"]),
        ("home", ["go home", "(go to|take me to) the home screen", "home screen"], ["home (pe jao|screen pe jao)", "ghar wali screen"]),
        ("recents", ["(show|open) (recent|recent apps)", "recent apps"], ["recent apps (dikhao|kholo)"]),
        ("notifications", ["(open|show|pull down) (my )?notifications", "check (my )?notifications"],
                          ["notification(s)? (kholo|dikhao)", "notifications (dikhao|check karo)"]),
        ("quick_settings", ["(open|show) quick settings"], ["quick settings (kholo|dikhao)"]),
        ("lock_screen", ["lock (the|my) (phone|screen)", "lock it"], ["phone lock (karo|kar do)", "screen lock kar do"])]:
    add(_many("navigate_phone", "en", {"action": action}, *en))
    add(_many("navigate_phone", "hi", {"action": action}, *hi))
add(_many("scroll", "en", {"direction": "down"}, "scroll down", "(go|move) down[ a bit]", "show me more"))
add(_many("scroll", "en", {"direction": "up"}, "scroll up", "(go|move) up[ a bit]", "back to the top"))
add(_many("scroll", "hi", {"direction": "down"}, "(neeche|niche) (scroll karo|karo|jao)", "thoda (neeche|niche)[ karo]"))
add(_many("scroll", "hi", {"direction": "up"}, "upar (scroll karo|karo|jao)", "thoda upar[ karo]"))
add(_many("read_screen", "en", {},
    "read (the|my|this) screen", "what does (the|this) screen say", "read (this|it) (out|aloud)[ to me]",
    "what's (written|on the screen)"))
add(_many("read_screen", "hi", {},
    "screen (padho|padh ke sunao)", "(ye|yeh) (padho|padh ke sunao)", "screen pe kya likha hai"))
add(_many("summarize_screen", "en", {},
    "(summarise|summarize) (this|the screen|this page)", "what is this (page|screen) about",
    "explain (this|what's on the screen)", "give me the gist of this (page|article)"))
add(_many("summarize_screen", "hi", {},
    "is (page|screen) ko summarise karo", "(ye|yeh) kya hai[,] samjhao", "is page ka (matlab|saar) batao",
    "screen pe jo hai uska (summary|saar) batao"))
add(_many("tap_on", "en", {},
    "tap (on )?{target}", "(click|press) (on )?(the )?{target}( button)?", "hit {target}", "select {target}"))
add(_many("tap_on", "hi", {},
    "{target} (pe|par) (tap|click) (karo|kar do)", "{target} (dabao|daba do)", "{target} wala button (dabao|daba do)"))

# ── camera / maps ──────────────────────────────────────────────────────────
add(_many("camera", "en", {"mode": "photo"}, "open the camera", "(take|click) a (photo|picture|pic)", "camera please"))
add(_many("camera", "en", {"mode": "selfie"}, "(take|click) a selfie", "open the (front|selfie) camera"))
add(_many("camera", "en", {"mode": "video"}, "(record|shoot|start recording) a video", "open the video camera"))
add(_many("camera", "en", {"mode": "scan"}, "scan (a|this) (qr code|document)", "open the (qr )?scanner"))
add(_many("camera", "hi", {"mode": "photo"}, "camera (kholo|khol do|chalu karo)", "(photo|pic|tasveer) (khicho|lo|le lo)"))
add(_many("camera", "hi", {"mode": "selfie"}, "selfie (lo|le lo|khicho)", "front camera (kholo|chalu karo)"))
add(_many("camera", "hi", {"mode": "video"}, "video (banao|record karo|shoot karo)"))
add(_many("camera", "hi", {"mode": "scan"}, "(qr code|scanner) (scan karo|kholo)"))
add(_many("navigate_to", "en", {},
    "(navigate|take me|get directions) to {place}", "how do i get to {place}", "directions to {place}",
    "show {place} on the map", "find {place} on (google )?maps", "start navigation to {place}"))
add(_many("navigate_to", "en", {"mode": "walking"}, "walking directions to {place}", "how do i walk to {place}"))
add(_many("navigate_to", "en", {"mode": "transit"}, "(how do i get|directions) to {place} by (metro|bus|public transport)"))
add(_many("navigate_to", "hi", {},
    "{place} (ka rasta batao|kaise jaun|tak le chalo)", "{place} ke liye (navigation|direction) (chalu karo|dikhao)",
    "maps pe {place} dikhao", "{place} jaana hai[,] rasta batao"))
add(_many("navigate_to", "hi", {"mode": "walking"}, "{place} paidal kaise jaun"))

# ── memory ─────────────────────────────────────────────────────────────────
add(_many("remember", "en", {},
    "remember (that )?{fact}", "(note|keep in mind) that {fact}", "don't forget (that )?{fact}",
    "save this[:] {fact}", "i want you to remember (that )?{fact}"))
add(_many("remember", "hi", {},
    "yaad rakhna (ki )?{fact}", "{fact}[,] yaad rakh lo", "ye yaad rakho[:] {fact}", "note kar lo ki {fact}"))
add(_many("recall", "en", {},
    "what('s| is) {recall}", "do you remember {recall}", "tell me {recall}", "what did i tell you about {recall}"))
add(_many("recall", "hi", {},
    "{recall} kya hai", "{recall} (batao|bata do)", "tumhe yaad hai {recall}", "maine {recall} ke baare mein kya bataya tha"))
add(_many("forget", "en", {}, "forget {recall}", "(delete|remove) what i said about {recall}"))
add(_many("forget", "hi", {}, "{recall} (bhool jao|bhul jao)", "{recall} wali baat (delete karo|hata do)"))

# ── translate / notes / laptop / language / conversation control ───────────
add(_many("translate", "en", {},
    "translate {text} (to|into) {lang_name}", "how do you say {text} in {lang_name}",
    "what is {text} in {lang_name}"))
add(_many("translate", "hi", {},
    "{text} ko {lang_name} mein (translate karo|batao)", "{lang_name} mein {text} kaise (bolte|kehte) hain"))
add(_many("create_note", "en", {},
    "(make|take|create) a note[:] {note}", "note (down|this)[:] {note}", "write down {note}", "add a note (saying|that) {note}"))
add(_many("create_note", "hi", {},
    "note (bana lo|likh lo)[:] {note}", "{note} (note kar lo|likh lo)", "ek note banao ki {note}"))
add(_many("laptop_command", "en", {},
    "{laptop_cmd} on (the|my) (laptop|computer|pc)", "on (the|my) (laptop|computer|pc)[,] {laptop_cmd}",
    "(tell|ask) (the|my) (laptop|pc) to {laptop_cmd}"))
add(_many("laptop_command", "hi", {},
    "(laptop|pc|computer) (pe|par|mein) {laptop_cmd}", "{laptop_cmd} (laptop|pc) (pe|par)"))
add(_many("set_language", "en", {"mode": "english_in"},
    "(switch|change) to english", "(talk|speak) (to me )?in english", "english (only|mode)[ please]"))
add(_many("set_language", "en", {"mode": "hinglish"},
    "(switch|change) to hinglish", "(talk|speak) (to me )?in hinglish", "hinglish mode"))
add(_many("set_language", "hi", {"mode": "hinglish"},
    "hinglish mein (baat karo|bolo)", "hindi mein baat karo"))
add(_many("set_language", "hi", {"mode": "english_in"},
    "english mein (baat karo|bolo)", "english mode (karo|chalu karo)"))
add(_many("end_conversation", "en", {"mode": "bye"},
    "bye", "bye bye", "goodbye", "that's all[ for now]", "see you", "thanks[,] bye"))
add(_many("end_conversation", "en", {"mode": "sleep"},
    "(go to )?sleep", "stop listening", "turn off (the )?wake word", "go to sleep (now|aeris)"))
add(_many("end_conversation", "hi", {"mode": "bye"},
    "(bas|bas karo)[ abhi]", "chalo bye", "theek hai bye", "abhi ke liye itna hi"))
add(_many("end_conversation", "hi", {"mode": "sleep"},
    "so jao", "(sona hai|ab so jao)", "sunna band karo"))
add(_many("cancel_task", "en", {},
    "stop (that|it|what you're doing)", "cancel (that|it|the task)", "never mind[,] stop", "abort"))
add(_many("cancel_task", "hi", {},
    "(ruko|ruk jao|rok do)", "(cancel|band) karo (ye|yeh) kaam", "rehne do[,] mat karo"))
