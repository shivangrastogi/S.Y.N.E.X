"""Unit-price comparison — which pack is cheaper per unit. Pure math, offline."""
from __future__ import annotations

import re
from typing import Optional

# qty units → factor to a base (ml for volume, g for weight). Comparison
# only makes sense within one dimension.
_UNIT = {
    "ml": ("vol", 1.0), "l": ("vol", 1000.0), "litre": ("vol", 1000.0),
    "liter": ("vol", 1000.0), "ltr": ("vol", 1000.0),
    "g": ("wt", 1.0), "gm": ("wt", 1.0), "gram": ("wt", 1.0),
    "kg": ("wt", 1000.0), "kilo": ("wt", 1000.0),
    "pcs": ("count", 1.0), "piece": ("count", 1.0), "pieces": ("count", 1.0),
    "unit": ("count", 1.0), "units": ("count", 1.0),
}

# "500ml for 40" / "1 litre 70 rupaye" / "250 g @ 30"
_OPTION_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(ml|l|litre|liter|ltr|kg|kilo|g|gm|gram|pcs|"
    r"pieces?|units?)\b[^\d]*?(\d+(?:\.\d+)?)",
    re.IGNORECASE)


def compare(text: str) -> Optional[str]:
    opts = []
    for m in _OPTION_RE.finditer(text or ""):
        qty = float(m.group(1))
        unit = m.group(2).lower()
        price = float(m.group(3))
        dim, factor = _UNIT.get(unit, ("count", 1.0))
        if qty <= 0:
            continue
        base_qty = qty * factor
        opts.append({"qty": qty, "unit": unit, "price": price,
                     "dim": dim, "per_base": price / base_qty})
    if len(opts) < 2:
        return None
    dims = {o["dim"] for o in opts}
    if len(dims) > 1:
        return ("Alag-alag units (jaise ml aur g) compare nahi ho sakte, "
                "sir — same type rakho.")
    opts.sort(key=lambda o: o["per_base"])
    best = opts[0]
    dim = best["dim"]
    per_label = {"vol": "per litre", "wt": "per kg", "count": "per piece"}[dim]
    per_mult = {"vol": 1000.0, "wt": 1000.0, "count": 1.0}[dim]

    def _line(o):
        pu = o["per_base"] * per_mult
        return f"{_fmt(o['qty'])}{o['unit']} @ {_fmt(o['price'])} = {_fmt(pu)}/{per_label.split()[-1]}"

    lines = [_line(o) for o in opts]
    save = (opts[1]["per_base"] - best["per_base"]) / opts[1]["per_base"] * 100
    return (f"Sasta: {_fmt(best['qty'])}{best['unit']} @ "
            f"{_fmt(best['price'])} ({_fmt(best['per_base'] * per_mult)} "
            f"{per_label}). " + " · ".join(lines)
            + (f"  ~{save:.0f}% cheaper." if save >= 1 else ""))


def _fmt(n: float) -> str:
    return str(int(n)) if abs(n - round(n)) < 1e-9 else f"{n:.2f}"
