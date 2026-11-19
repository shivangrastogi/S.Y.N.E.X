"""MASSIVE (Amazon, CC-BY-4.0) → neutral JSONL.

    py -m brain.convert.massive --tar amazon-massive-dataset-1.1.tar.gz --out out/converted
    (or --tar https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz)

The Hugging Face loader for MASSIVE relies on a dataset script, which newer
`datasets` versions no longer run — so this reads the official tarball:
<version>/data/<locale>.jsonl with fields id, locale, partition, scenario,
intent, utt, annot_utt ("wake me up at [time : five am] [date : this week]").

Default locale en-US. (hi-IN is Devanagari Hindi — our STT emits Roman
script, so it is not used by default.) partition train+dev → train,
test → eval.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import re
import tarfile
import urllib.request

from .common import call, record, write

SLOT = re.compile(r"\[(\w+) : ([^\]]+)\]")

LIVE = {"news_query", "weather_query", "qa_stock", "qa_currency", "transport_query",
        "transport_traffic"}
KNOW = {"qa_factoid", "qa_definition", "cooking_recipe", "recommendation_events",
        "recommendation_locations", "recommendation_movies"}
MEDIA = {"music_settings": None}


def slots_of(annot: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for k, v in SLOT.findall(annot):
        out.setdefault(k, []).append(v.strip())
    return out


def first(sl, *names):
    for n in names:
        if sl.get(n):
            return sl[n][0]
    return None


def to_contract(intent: str, utt: str, sl: dict) -> dict | None:
    if intent == "alarm_set":
        t = first(sl, "time")
        if not t:
            return {"type": "ask", "text": "For what time?", "pending": "set_alarm"}
        return call("set_alarm", time=t, days=first(sl, "date"))
    vol = {"audio_volume_up": "up", "audio_volume_down": "down", "audio_volume_mute": "mute"}
    if intent in vol:
        return call("volume", action=vol[intent])
    if intent == "calendar_set":
        title = first(sl, "event_name", "meeting_type")
        if not title:
            return None
        d, t = first(sl, "date"), first(sl, "time")
        when = None
        if d and t:
            for joined in (f"{d} at {t}", f"{d} {t}", f"{t} {d}", f"{t} on {d}"):
                if joined.lower() in utt.lower():
                    when = joined
                    break
        when = when or d or t
        return call("create_calendar_event", title=title, when=when, location=first(sl, "place_name"))
    if intent == "datetime_query":
        if first(sl, "place_name", "timezone"):
            return {"type": "escalate", "reason": "live_info", "query": utt}
        u = utt.lower()
        what = "time" if "time" in u else "date" if "date" in u else "day" if "day" in u else None
        return call("date_time", what=what) if what else None
    if intent == "email_sendemail":
        if "mail" not in utt.lower():
            return None  # MASSIVE's email labels are noisy when "mail" isn't said
        to = first(sl, "person", "relation", "email_address")
        return call("send_email", to=to) if to else None
    if intent in ("play_music", "play_radio", "play_podcasts", "play_audiobook"):
        q = first(sl, "song_name", "artist_name", "playlist_name", "music_genre",
                  "radio_name", "podcast_name", "audiobook_name", "podcast_descriptor",
                  "music_descriptor")
        song, artist = first(sl, "song_name"), first(sl, "artist_name")
        if song and artist and f"{song} by {artist}".lower() in utt.lower():
            q = f"{song} by {artist}"  # keep the artist: "sleepyhead by passion pit"
        app = (first(sl, "app_name", "media_type") or "").lower()
        app = "spotify" if "spotify" in app else "youtube" if "youtube" in app else None
        if q is None and set(sl) - {"app_name", "media_type", "player_setting"}:
            return None
        return call("play_music", query=q, app=app)
    if intent == "qa_maths":
        expr = re.sub(r"^(what is|what's|calculate|how much is|compute|tell me)\s+", "", utt.strip(),
                      flags=re.I).rstrip("?. ")
        return call("calculate", expression=expr) if expr else None
    if intent in LIVE:
        return {"type": "escalate", "reason": "live_info", "query": utt}
    if intent in KNOW:
        return {"type": "escalate", "reason": "knowledge", "query": utt}
    return None


def _open_tar(src: str) -> tarfile.TarFile:
    if src.startswith("http"):
        data = urllib.request.urlopen(src).read()  # ~40 MB
        return tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    return tarfile.open(src, mode="r:gz")


def convert(src: str, out_dir: str, locales=("en-US",), seed: int = 1):
    rng = random.Random(seed)
    train, evals, skipped = [], [], 0
    with _open_tar(src) as tar:
        members = {m.name: m for m in tar.getmembers()}
        for loc in locales:
            name = next((n for n in members if n.endswith(f"/data/{loc}.jsonl")), None)
            if name is None:
                print(f"  locale {loc} not in archive")
                continue
            for ln in tar.extractfile(members[name]).read().decode("utf-8").splitlines():
                row = json.loads(ln)
                out = to_contract(row["intent"], row["utt"], slots_of(row["annot_utt"]))
                if out is None:
                    skipped += 1
                    continue
                gold = [c["name"] for c in out.get("calls", [])] + ([out["pending"]] if out.get("pending") else [])
                is_eval = row["partition"] == "test"
                rec = record(f"massive-{loc}-{row['id']}", f"massive/{loc}",
                             [{"role": "user", "content": row["utt"]}, {"role": "assistant", "content": out}],
                             rng, lang="en", gold=gold, split="test" if is_eval else "train",
                             meta={"intent": row["intent"]})
                (evals if is_eval else train).append(rec)
    n1 = write(os.path.join(out_dir, "massive.train.jsonl"), train)
    n2 = write(os.path.join(out_dir, "massive.eval.jsonl"), evals)
    print(f"massive: train {n1}, eval {n2}, skipped (unmapped intents) {skipped}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tar", required=True, help="path or URL of amazon-massive-dataset-1.x.tar.gz")
    ap.add_argument("--out", default="out/converted")
    ap.add_argument("--locales", nargs="+", default=["en-US"])
    a = ap.parse_args(argv)
    convert(a.tar, a.out, tuple(a.locales))


if __name__ == "__main__":
    main()
