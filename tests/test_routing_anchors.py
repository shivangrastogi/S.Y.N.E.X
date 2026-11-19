"""Locks in the deterministic routing layer (core/brain._ANCHORS +
_is_plain_arithmetic) so the ~15 anchors added over the 2026-08-01 routing pass
can't silently regress. Pure functions — no engine, runs in the fast lane.

Each anchor should FIRE for its target phrasings and NOT fire (return None) for
the over-catch traps that motivated its exclude clause. See
docs/ROUTING_ACCURACY_AUDIT.md.
"""
from __future__ import annotations

import pytest

from core.brain import _anchor_intent, _is_plain_arithmetic


# ── Arithmetic detector ─────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "12 plus 37 kitna hai", "25 into 4 kitna hota hai", "144 divided by 12",
    "999 minus 88", "18 ka 20 percent", "2 ki power 10 kya hai",
    "150 multiply by 3", "20 percent of 2000", "45 aur 55 add karo",
])
def test_plain_arithmetic_fires(text):
    assert _is_plain_arithmetic(text) is True


@pytest.mark.parametrize("text", [
    "kal 9 baje reminder set karo",   # a time, not a sum
    "5 minute ka timer",              # single number
    "volume 10 percent badhao",       # single number
    "meeting on 2026-08-01",          # date hyphens, not subtraction
    "calculate the tip on 800",       # domain word: tip
    "15 percent gst on 500",          # domain word: gst
    "gcd of 12 and 18",               # domain word: gcd
    "amazon kholo",                   # no numbers
])
def test_plain_arithmetic_does_not_fire(text):
    assert _is_plain_arithmetic(text) is False


# ── Command anchors: (text, expected intent) ────────────────────────────
@pytest.mark.parametrize("text,intent", [
    ("time kya hua", "get_time"),
    ("kitne baje hain", "get_time"),
    ("time batao", "get_time"),
    ("current time", "get_time"),
    ("google karo best laptops", "search_web"),
    ("web pe dhundo iphone price", "search_web"),
    ("iska matlab batao serendipity", "define_word"),
    ("define karo empathy", "define_word"),
    ("gcd of 48 and 36", "gcd_lcm"),
    ("hcf of 24 36", "gcd_lcm"),
    ("is 29 prime", "number_properties"),
    ("factors of 24", "number_properties"),
    ("uppercase karo hello", "text_transform"),
    ("reverse abcde", "text_transform"),
    ("count characters in hello", "count_chars"),
    ("who are you", "who_are_you"),
    ("what is your name", "who_are_you"),
    ("tell me about yourself", "who_are_you"),
    ("cpu usage kitna hai", "system_stats"),
    ("disk space kitna bacha hai", "system_stats"),
    ("1 hour in minutes", "unit_convert"),
    ("2 days in hours", "unit_convert"),
    ("42 to binary", "base_convert"),
    ("binary of 42", "base_convert"),
    ("generate a uuid", "uuid_generate"),
    # clipboard: mode-word commands must hit the dedicated clipboard skills,
    # NOT the inline text_transform/count skills (which would mangle the literal
    # word "clipboard" instead of the clipboard's contents).
    ("clipboard uppercase karo", "clipboard_transform"),
    ("clipboard reverse karo", "clipboard_transform"),
    ("clipboard slug karo", "clipboard_transform"),
    ("clipboard me kya hai", "clipboard_paste"),
    ("what's in the clipboard", "clipboard_paste"),
    ("paste the clipboard", "clipboard_paste"),
    # file search: prefix AND postfix-Hinglish phrasings must hit file_search
    # ("productivity file kahaan hai" was answering with a currency conversion).
    ("productivity file kahaan hai", "file_search"),
    ("resume file kahan hai", "file_search"),
    ("locate the file config", "file_search"),
    ("find my files", "file_search"),
    ("file dhundo report", "file_search"),
    # "kill <name>" → kill_process (was mis-routing to file_search).
    ("kill firefox", "kill_process"),
    ("kill zzqqxx", "kill_process"),
    ("kill the discord app", "kill_process"),
    ("kill chrome.exe", "kill_process"),
    # entertainment/conversational — clear keyword → the (LLM-backed) skill,
    # was scattering to play_music / current_time / keep_awake_on / create_note.
    ("ek acha joke sunao", "tell_joke"),
    ("chutkula sunao yaar", "tell_joke"),
    ("koi pj sunao", "tell_joke"),
    ("bedtime story sunao", "tell_story"),
    ("koi interesting kahani batao", "tell_story"),
    ("ek motivational story sunao", "tell_story"),  # story wins over motivate cue
    ("mera mood theek karo", "motivate_me"),
    ("ek pep talk do", "motivate_me"),
    ("aaj mann nahi lag raha motivate karo", "motivate_me"),
    # volume + music core actions — the modifier disambiguates up/down/mute
    # (was mis-routing to the OPPOSITE direction, or to create_note).
    ("volume tez karo", "volume_up"),
    ("sound zyada karo", "volume_up"),
    ("louder please", "volume_up"),
    ("awaaz dheemi karo", "volume_down"),
    ("aawaz kam kar do", "volume_down"),
    ("turn it down", "volume_down"),
    ("sound band karo", "volume_mute"),
    ("chup karo", "volume_mute"),
    ("awaaz gayab karo", "volume_mute"),
    ("arijit singh ka gaana bajao", "play_music"),
    ("music start karo", "play_music"),
    ("gaana suna do", "play_music"),
    # "what can you do" / capability overview → help_catalog.
    ("help", "help_catalog"),
    ("what can you do", "help_catalog"),
    ("kya kya kar sakte ho", "help_catalog"),
    ("mere jarvis mein kya hai", "help_catalog"),
    ("features batao", "help_catalog"),
    ("show me your skills", "help_catalog"),
    # category drill-down requests also reach the catalog.
    ("system commands kya hain", "help_catalog"),
    ("math commands", "help_catalog"),
    ("voice commands", "help_catalog"),
    # 2026-09-15 pass: each row was a measured mis-route.
    ("meri english theek karo", "fix_grammar"),          # was day_of_week
    ("sentence sahi kar do", "fix_grammar"),             # was volume_up
    ("proofread this sentence", "fix_grammar"),
    ("galtiyan theek karo is text ki", "fix_grammar"),
    ("zara lock kar do", "lock_screen"),                 # was volume_mute
    ("AERIS screen lock karo", "lock_screen"),           # was open_settings_panel
    ("lock ho jao", "lock_screen"),                      # was append_note
    ("shutdown karo", "shutdown_pc"),                    # was cancel_shutdown
    ("power off karo", "shutdown_pc"),                   # was factorial_power
    ("band kar do laptop", "shutdown_pc"),               # was laptop_screen_share
    ("restart karo pc", "restart_pc"),
    ("netflix kholo", "open_in_browser"),                # was youtube_jump
    ("reddit kholo", "open_in_browser"),                 # was tab_switch
    ("flipkart ki site kholo", "open_in_browser"),
    ("open linkedin", "open_in_browser"),                # was clipboard_open_url
    ("root 81 kya hai", "quick_calc"),                   # was synonyms_antonyms
    ("square root of 256", "quick_calc"),
    ("5 factorial kya hai", "factorial_power"),          # was focus_deep_status
    ("square of 17", "factorial_power"),
    ("youtube pe song laga do", "play_youtube"),         # was play_music
    ("youtube pe motivational video", "play_youtube"),   # was motivate_me
    ("youtube kholo aur music chalao", "play_youtube"),
    ("dhundo ipl schedule", "search_web"),               # was volume_down
    ("grammar mistake fix karo", "fix_grammar"),         # was shorten_text
    ("make this grammatically correct", "fix_grammar"),  # was translate_to
    ("make me laugh", "tell_joke"),                      # was i_am_master
    ("kuch hasane wala bolo", "tell_joke"),
    ("inspire me please", "motivate_me"),                # was uuid_generate
    ("give me a boost", "motivate_me"),                  # was uuid_generate
    ("kuch hausla badhane wala bolo", "motivate_me"),    # was calculate
    ("demotivated feel kar raha hoon", "motivate_me"),
    ("pc ko sula do", "sleep_pc"),                       # was pomodoro_status
    ("leetcode kholo", "open_in_browser"),               # was open_app
    ("open whatsapp web", "open_in_browser"),            # was open_app
])
def test_anchor_fires(text, intent):
    assert _anchor_intent(text) == intent


# ── Over-catch traps: must NOT anchor (or must anchor elsewhere) ─────────
@pytest.mark.parametrize("text", [
    "world time in tokyo",             # get_time exclude
    "set a timer for 5 min",           # get_time exclude
    "google me dekho weather",         # search_web exclude (weather)
    "what is my name",                 # who_are_you exclude (user's name)
    "who are you gonna call",          # who_are_you exclude (gonna)
    "prime minister kaun hai",         # number_properties exclude (minister)
    "reverse the number 12345",        # text_transform exclude (number)
    "length of the meeting",           # count_chars does NOT include "length of"
    "free up disk space",              # system_stats exclude (cleanup)
    "5 minute ka timer",               # unit_convert exclude (real timer)
    "remind me in 5 minutes",          # unit_convert exclude (reminder)
    "good morning",                    # greetings untouched
    "office kahaan hai",               # file_search needs the word "file"
    "mera phone kahaan hai",           # a thing, not a file
    "file kholo report",               # file_search exclude (open, not search)
    "file delete karo",                # file_search exclude (delete, not search)
    "kill time",                       # kill_process idiom exclude
    "kill the lights",                 # kill_process idiom exclude
    "kill the music",                  # kill_process idiom exclude
    "kill the mood",                   # kill_process idiom exclude
    "instagram story dekho",           # tell_story exclude (social story)
    "success story sunao mujhe apni",  # tell_story exclude (success story)
    "news story padho",                # tell_story exclude (news story)
    "practical joke ideas",            # tell_joke exclude
    "gaana band karo",                 # play_music exclude (band = stop, not play)
    "music band karo",                 # play_music exclude
    "gaana rok do",                    # play_music exclude (rok = stop)
    "help me open chrome",             # help_catalog exclude ("help me <do X>")
    "help me write an email",          # help_catalog exclude
    "lock after 5 minutes",            # lock_screen: scheduled → lock_after
    "unlock karo",                     # lock_screen exclude
    "caps lock band karo",             # lock_screen exclude
    "shutdown cancel karo",            # shutdown_pc exclude (the opposite!)
    "shutdown mat karo",               # shutdown_pc exclude
    "shutdown 30 minute baad",         # shutdown_pc: a schedule, not now
    "chrome restart karo",             # restart_pc: an app, not the PC
    "aeris restart karo",              # restart_pc: the assistant, not the PC
    "instagram app kholo",             # open_in_browser: explicit app
    "chrome me gmail kholo",           # open_in_browser anchor stays out; skill patterns own it
    "youtube channel ke ideas do",     # play_youtube exclude → brainstorm guard
    "mujhe grammar school yaad hai",   # fix_grammar needs a fix verb, not the bare word
    "energy calculate karo 5 kwh",     # motivate_me exclude (energy_calc)
    "pc sleep after 10 minutes",       # sleep_pc: scheduled, not now
])
def test_anchor_does_not_overcatch(text):
    got = _anchor_intent(text)
    # Either no anchor, or (for the few that legitimately route elsewhere) NOT
    # the intent the trap was guarding against.
    assert got in (None, "set_reminder", "set_timer")
