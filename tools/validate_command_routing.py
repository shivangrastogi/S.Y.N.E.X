"""Measure routing accuracy on hand-curated phrasings.

Runs every example in data/command_examples.json through the engine's real
routing, ``JarvisMainEngine.route()`` (repair alias, exact pattern, subspan
scan, app gazetteer, safety guard), and checks where each one lands.

    python tools/validate_command_routing.py

Two numbers per command and overall:

  strict    the landing intent is the example's label
  accepted  ...or it is listed for that label under "_also_ok": a
            better-owned skill with the same result (screenshot_full for
            take_screenshot). Only non-accepted landings are listed as
            mis-routes.

Changes nothing on disk and needs no retrain. History of the numbers is in
docs/ROUTING_ACCURACY_AUDIT.md (50% on 2026-07-27).
"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("AERIS_DISABLE_BRIDGE", "1")


def load_examples(path):
    """Return (examples, also_ok). Keys starting with "_" are metadata."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    examples = {k: v for k, v in data.items()
                if not k.startswith("_") and isinstance(v, list)}
    also_ok = {k: set(v) for k, v in (data.get("_also_ok") or {}).items()
               if isinstance(v, list)}
    return examples, also_ok


def main():
    sys.path.insert(0, _ROOT)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from core.main_engine import JarvisMainEngine
    eng = JarvisMainEngine(stt="SKIP", tts="SKIP", verbose=False, lazy=True)
    for _ in eng.setup_iter():
        pass
    print("engine ready\n", flush=True)

    examples, also_ok = load_examples(
        os.path.join(_ROOT, "data", "command_examples.json"))

    total = strict = accepted = 0
    misroutes = {}
    for cmd, phrases in examples.items():
        ok_set = {cmd} | also_ok.get(cmd, set())
        c_strict = c_acc = 0
        bad = []
        for ex in phrases:
            try:
                got = eng.route(ex)[0].intent
            except Exception as e:
                got = f"<ERR {e}>"
            c_strict += got == cmd
            if got in ok_set:
                c_acc += 1
            else:
                bad.append((ex, got))
        n = len(phrases)
        total += n
        strict += c_strict
        accepted += c_acc
        pct = 100.0 * c_acc / max(1, n)
        print(f"[{'OK ' if pct >= 80 else 'LOW'}] {cmd:18s} "
              f"accepted {c_acc:2d}/{n:2d} ({pct:3.0f}%)   strict {c_strict:2d}/{n:2d}",
              flush=True)
        if bad:
            misroutes[cmd] = bad

    print(f"\nOVERALL accepted: {accepted}/{total} = {100.0 * accepted / max(1, total):.1f}%")
    print(f"OVERALL strict:   {strict}/{total} = {100.0 * strict / max(1, total):.1f}%\n")
    print("=== mis-routes (not accepted) ===")
    for cmd, bad in misroutes.items():
        print(f"\n{cmd}:")
        for ex, got in bad:
            print(f"   '{ex}'  ->  {got}")


if __name__ == "__main__":
    main()
