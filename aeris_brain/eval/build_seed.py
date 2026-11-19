"""Build eval/seed_real.jsonl — hand-written, messy, real-style utterances.

This is the RELEASE GATE (plan §6.6.1): never trained on, never generated
from templates. Items 1-4 are real 2026-10-17 phone transcripts; the rest
are written to sound like the user (English, Hinglish, fillers, STT slips).
Grow it with your own logged utterances — that's what makes it honest.

    py -m eval.build_seed          (from aeris_brain/)

For reply/ask/plan/escalate only the TYPE (and ask.pending / escalate
reason) is scored, so their texts here are just plausible examples.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
from brain.contract import load_tools, make_call, validate  # noqa: E402

TOOLS = load_tools()


def C(*calls):
    return make_call(TOOLS, *calls)


def ASK(pending, text="?"):
    return {"type": "ask", "text": text, "pending": pending}


def REPLY(text="ok"):
    return {"type": "reply", "text": text}


def ESC(reason, query):
    return {"type": "escalate", "reason": reason, "query": query}


def PLAN(goal):
    return {"type": "plan", "goal": goal, "steps": ["step 1", "step 2"]}


SEED = [
    # ── real transcripts, 2026-10-17 ──────────────────────────────────
    ("I want to do send a WhatsApp message on this number 7300 978845 hi",
     C(("send_message", {"number": "7300 978845", "message": "hi", "app": "whatsapp"}))),
    ("hi how are you", REPLY()),
    ("Hi Jarvis firstly generate image of a person standing in kitchen and send to my Ravi on whatsapp",
     PLAN("image to Ravi")),
    ("Gemini mein ek sunset ki photo banao", PLAN("sunset image in Gemini")),
    # ── commands, English ─────────────────────────────────────────────
    ("hey aeris can you like turn on the torch", C(("flashlight", {"state": "on"}))),
    ("its so dark yaar switch on flash light", C(("flashlight", {"state": "on"}))),
    ("okay switch the torch off now", C(("flashlight", {"state": "off"}))),
    ("make it a bit louder", C(("volume", {"action": "up"}))),
    ("too loud bring it down", C(("volume", {"action": "down"}))),
    ("put an alarm for 6:45 tomorrow morning", C(("set_alarm", {"time": "6:45", "days": "tomorrow morning"}))),
    ("wake me up at 5 30 am", C(("set_alarm", {"time": "5 30 am"}))),
    ("timer 12 minutes for the maggi", C(("set_timer", {"duration": "12 minutes", "label": "maggi"}))),
    ("start a timer of two minutes", C(("set_timer", {"duration": "two minutes"}))),
    ("call papa", C(("call", {"contact": "papa"}))),
    ("can you call Shivang Rastogi please", C(("call", {"contact": "Shivang Rastogi"}))),
    ("dial 98110 23456", C(("call", {"number": "98110 23456"}))),
    ("video call Priya on whatsapp", C(("call", {"contact": "Priya", "app": "whatsapp", "video": True}))),
    ("whatsapp Rahul that I'll be there by 8", C(("send_message", {"contact": "Rahul", "message": "I'll be there by 8", "app": "whatsapp"}))),
    ("send a message to boss saying I am on leave today", C(("send_message", {"contact": "boss", "message": "I am on leave today"}))),
    ("text mom reached safely", C(("send_message", {"contact": "mom", "message": "reached safely"}))),
    ("open insta", C(("open_app", {"app": "insta"}))),
    ("launch phone pe", C(("open_app", {"app": "phone pe"}))),
    ("open the zepto app", C(("open_app", {"app": "zepto"}))),
    ("play arijit singh songs", C(("play_music", {"query": "arijit singh songs"}))),
    ("play kesariya on spotify", C(("play_music", {"query": "kesariya", "app": "spotify"}))),
    ("next song please", C(("media_control", {"action": "next"}))),
    ("pause it", C(("media_control", {"action": "pause"}))),
    ("search for best biryani near me", C(("web_search", {"query": "best biryani near me", "engine": "google"}))),
    ("look up flutter riverpod tutorial on youtube", C(("web_search", {"query": "flutter riverpod tutorial", "engine": "youtube"}))),
    ("what's the time", C(("date_time", {"what": "time"}))),
    ("which day is today", C(("date_time", {"what": "day"}))),
    ("battery kitna hai bro", C(("battery_status", {}))),
    ("how much battery do I have", C(("battery_status", {}))),
    ("what is 18 percent of 2450", C(("calculate", {"expression": "18 percent of 2450"}))),
    ("turn off wifi", C(("toggle_setting", {"setting": "wifi", "state": "off"}))),
    ("switch on bluetooth i want to connect my earbuds", C(("toggle_setting", {"setting": "bluetooth", "state": "on"}))),
    ("put the phone on do not disturb", C(("toggle_setting", {"setting": "dnd", "state": "on"}))),
    ("take a screenshot", C(("take_screenshot", {}))),
    ("read whats on the screen", C(("read_screen", {}))),
    ("summarise this article for me", C(("summarize_screen", {}))),
    ("tap on Allow", C(("tap_on", {"target": "Allow"}))),
    ("go back", C(("navigate_phone", {"action": "back"}))),
    ("navigate to India Gate", C(("navigate_to", {"destination": "India Gate"}))),
    ("remember that my locker code is 4471", C(("remember", {"fact": "my locker code is 4471"}))),
    ("on the laptop open vs code", C(("laptop_command", {"command": "open vs code"}))),
    ("bye", C(("end_conversation", {"mode": "bye"}))),
    ("go to sleep", C(("end_conversation", {"mode": "sleep"}))),
    ("set an alarm for 7 and turn off the torch",
     C(("set_alarm", {"time": "7"}), ("flashlight", {"state": "off"}))),
    # ── commands, Hinglish ────────────────────────────────────────────
    ("torch jala do yaar", C(("flashlight", {"state": "on"}))),
    ("awaaz thoda kam karo", C(("volume", {"action": "down"}))),
    ("subah 6 baje utha dena", C(("set_alarm", {"time": "subah 6 baje"}))),
    ("kal subah saade 5 baje ka alarm laga do", C(("set_alarm", {"time": "saade 5 baje", "days": "kal subah"}))),
    ("10 minute ka timer lagao", C(("set_timer", {"duration": "10 minute"}))),
    ("mummy ko phone lagao", C(("call", {"contact": "mummy"}))),
    ("bhaiya ko video call karo", C(("call", {"contact": "bhaiya", "video": True}))),
    ("Neha ko whatsapp pe bolo ki main 5 min mein aa raha hoon",
     C(("send_message", {"contact": "Neha", "message": "main 5 min mein aa raha hoon", "app": "whatsapp"}))),
    ("papa ko message karo ki gaadi service pe de di",
     C(("send_message", {"contact": "papa", "message": "gaadi service pe de di"}))),
    ("is number pe call karo 70112 34567", C(("call", {"number": "70112 34567"}))),
    ("youtube kholo", C(("open_app", {"app": "youtube"}))),
    ("swiggy khol do jaldi", C(("open_app", {"app": "swiggy"}))),
    ("purane gaane bajao", C(("play_music", {"query": "purane gaane"}))),
    ("agla gaana", C(("media_control", {"action": "next"}))),
    ("google pe dhundo petrol pump near me", C(("web_search", {"query": "petrol pump near me", "engine": "google"}))),
    ("kitne baje hain", C(("date_time", {"what": "time"}))),
    ("aaj date kya hai", C(("date_time", {"what": "date"}))),
    ("wifi band karo", C(("toggle_setting", {"setting": "wifi", "state": "off"}))),
    ("screenshot le lo", C(("take_screenshot", {}))),
    ("screen padh ke sunao", C(("read_screen", {}))),
    ("wapas jao", C(("navigate_phone", {"action": "back"}))),
    ("connaught place ka rasta batao", C(("navigate_to", {"destination": "connaught place"}))),
    ("yaad rakhna gaadi B2 mein park ki hai", C(("remember", {"fact": "gaadi B2 mein park ki hai"}))),
    ("laptop pe chrome kholo", C(("laptop_command", {"command": "chrome kholo"}))),
    ("so jao", C(("end_conversation", {"mode": "sleep"}))),
    ("torch on karo aur volume full kar do",
     C(("flashlight", {"state": "on"}), ("volume", {"action": "max"}))),
    # ── clarify (ask) ─────────────────────────────────────────────────
    ("message Ravi", ASK("send_message")),
    ("set an alarm", ASK("set_alarm")),
    ("Amit ko whatsapp karo", ASK("send_message")),
    ("call karo", ASK("call")),
    ("timer laga do", ASK("set_timer")),
    # ── escalate (incl. hard negatives) ───────────────────────────────
    ("what's the weather like today", ESC("live_info", "what's the weather like today")),
    ("kal baarish hogi kya", ESC("live_info", "kal baarish hogi kya")),
    ("who won yesterday's ipl match", ESC("live_info", "who won yesterday's ipl match")),
    ("what is whatsapp actually", ESC("knowledge", "what is whatsapp actually")),
    ("torch ka avishkar kisne kiya tha", ESC("knowledge", "torch ka avishkar kisne kiya tha")),
    ("what time is it in New York", ESC("live_info", "what time is it in New York")),
    ("explain how neural networks learn", ESC("knowledge", "explain how neural networks learn")),
    ("write a leave application for my office", ESC("complex", "write a leave application for my office")),
    ("send 2000 rupees to Rahul on gpay", ESC("no_tool", "send 2000 rupees to Rahul on gpay")),
    # ── small talk ────────────────────────────────────────────────────
    ("thanks aeris", REPLY()),
    ("kaise ho", REPLY()),
    ("tum kaun ho", REPLY()),
    ("good night", REPLY()),
    ("ek joke sunao", REPLY()),
    # ── plans ─────────────────────────────────────────────────────────
    ("chatgpt se pucho aaj dinner mein kya banau aur bata do", PLAN("ask ChatGPT about dinner")),
    ("book an uber to the airport", PLAN("cab to airport")),
    ("screenshot lo aur didi ko whatsapp kar do", PLAN("screenshot to didi")),
]

# which escalate/reply items carry no grounded spans (validated loosely)


def main():
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_real.jsonl")
    bad = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for i, (text, gold) in enumerate(SEED, 1):
            errs = validate(gold, TOOLS, user_text=text, grounded=True)
            if errs:
                bad += 1
                print(f"#{i} INVALID: {text!r}: {errs}")
                continue
            rec = {"id": f"seed-{i:04d}", "split": "test", "source": "seed_real",
                   "family": gold["type"], "lang": None, "prompt_lang": "match",
                   "tools": list(TOOLS), "now": "Friday 17 October 2026, 18:40",
                   "messages": [{"role": "user", "content": text},
                                {"role": "assistant", "content": gold}]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"wrote {len(SEED) - bad} items -> {out_path}" + (f" ({bad} invalid skipped)" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
