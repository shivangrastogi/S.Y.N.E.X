"""Zip the aeris_brain code for Colab (upload to MyDrive/mobile aeris/).

    py -m scripts.pack     →  dist/aeris_brain_code.zip

Includes code, schema, eval sets, tests and notebooks. Never includes
out/ (generated data), private/ (your contacts/apps) or dist/.
"""
from __future__ import annotations

import os
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
SKIP_DIRS = {"out", "private", "dist", "__pycache__", ".pytest_cache"}


def main():
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    dst = os.path.join(ROOT, "dist", "aeris_brain_code.zip")
    n = 0
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, files in os.walk(ROOT):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in files:
                if fn.endswith((".pyc", ".zip")):
                    continue
                full = os.path.join(dirpath, fn)
                arc = os.path.join("aeris_brain", os.path.relpath(full, ROOT))
                z.write(full, arc)
                n += 1
    print(f"{n} files -> {dst} ({os.path.getsize(dst) // 1024} KB)")


if __name__ == "__main__":
    main()
