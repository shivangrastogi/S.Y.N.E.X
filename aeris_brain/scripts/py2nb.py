"""notebooks/src/*.py (percent format) → notebooks/*.ipynb for Colab.

    py -m scripts.py2nb

Cells start with "# %%"; "# %% [markdown]" cells have their "# " prefixes
stripped. The .py files are the source of truth (reviewable diffs); the
.ipynb files are generated — never edit them by hand.
"""
from __future__ import annotations

import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, os.pardir, "notebooks", "src")
DST = os.path.join(HERE, os.pardir, "notebooks")


def cells_of(text: str) -> list[dict]:
    cells, kind, buf = [], None, []

    def flush():
        if kind is None:
            return
        lines = buf[:]
        while lines and not lines[-1].strip():
            lines.pop()
        while lines and not lines[0].strip():
            lines.pop(0)
        if not lines:
            return
        if kind == "markdown":
            lines = [ln[2:] if ln.startswith("# ") else ln.lstrip("#") for ln in lines]
        src = [ln + "\n" for ln in lines]
        src[-1] = src[-1].rstrip("\n")
        cell = {"cell_type": kind, "metadata": {}, "source": src}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        cells.append(cell)

    for ln in text.splitlines():
        if ln.startswith("# %%"):
            flush()
            kind = "markdown" if "[markdown]" in ln else "code"
            buf = []
        else:
            buf.append(ln)
    flush()
    return cells


def main():
    for path in sorted(glob.glob(os.path.join(SRC, "*.py"))):
        nb = {"cells": cells_of(open(path, encoding="utf-8").read()),
              "metadata": {"accelerator": "GPU", "colab": {"provenance": []},
                           "kernelspec": {"display_name": "Python 3", "name": "python3"},
                           "language_info": {"name": "python"}},
              "nbformat": 4, "nbformat_minor": 0}
        out = os.path.join(DST, os.path.basename(path).replace(".py", ".ipynb"))
        with open(out, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"{os.path.basename(out)}: {len(nb['cells'])} cells")


if __name__ == "__main__":
    main()
