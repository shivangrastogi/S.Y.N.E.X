"""Measure routing accuracy: run every hand-curated example in
data/command_examples.json through the REAL classifier and check it routes to
its intended command. Prints per-command accuracy + mis-routes.

    python validate_command_routing.py

Re-run after trimming the corpus / retraining to track accuracy toward 100%.
See docs/ROUTING_ACCURACY_AUDIT.md for the baseline (50% on 2026-07-27).
"""
import os
import sys
import json

_ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")


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
    brain = eng.brain
    print("engine ready\n", flush=True)

    path = os.path.join(_ROOT, "data", "command_examples.json")
    cur = json.load(open(path, encoding="utf-8"))
    cur = {k: v for k, v in cur.items() if not k.startswith("_")}

    total = ok = 0
    misroutes = {}
    for cmd, examples in cur.items():
        c_ok, bad = 0, []
        for ex in examples:
            try:
                # Measure the REAL routing the user gets: the raw classifier
                # PLUS the engine's _guard_dangerous_route safety net (which
                # rescues absurd/destructive mis-routes). Measuring brain.predict
                # alone understates end-to-end accuracy, since the guard fires in
                # process_text, not inside predict.
                pred = brain.predict(ex)
                got = eng._guard_dangerous_route(ex, pred).intent
            except Exception as e:
                got = f"<ERR {e}>"
            if got == cmd:
                c_ok += 1
            else:
                bad.append((ex, got))
        total += len(examples)
        ok += c_ok
        acc = 100.0 * c_ok / max(1, len(examples))
        print(f"[{'OK ' if acc >= 80 else 'LOW'}] {cmd:18s} {c_ok:2d}/{len(examples):2d}  ({acc:.0f}%)", flush=True)
        if bad:
            misroutes[cmd] = bad

    print(f"\nOVERALL: {ok}/{total} = {100.0 * ok / max(1, total):.1f}% route correctly\n")
    print("=== mis-routing examples ===")
    for cmd, bad in misroutes.items():
        print(f"\n{cmd}:")
        for ex, got in bad[:15]:
            print(f"   '{ex}'  ->  {got}")


if __name__ == "__main__":
    main()
