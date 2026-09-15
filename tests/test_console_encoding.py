"""Console output must survive a cp1252 Windows console (§6.37).

This has now bitten three times:

1. `core/tts.py` — a whole helper (`_clean_for_speech`) exists because emoji in
   a reply crashed the log/console stream with
   `'charmap' codec can't encode`.
2. `gen_flags_doc.py` (§6.36) — printed a `→` in a hint and died.
3. `run_voice_split.py` — printed a `✓` when reporting that the microphone had
   stayed closed. That is the **live harness the user was asked to run**, and
   it would have crashed at the exact moment it said the thing worked.

The third one is why this is a test rather than another fix. A crash in a
diagnostic tool is worse than a crash anywhere else: it destroys the evidence
someone was collecting, and it does it precisely on the success path, which is
the path nobody thinks to test.

Scope is deliberately narrow — **literal strings passed to `print()`**. Logging
goes through handlers that can be configured with an encoding and errors
policy; `print` goes straight at whatever the console is, which on this machine
is cp1252. Runtime *values* (a filename, a user's utterance) can obviously
contain anything and are not this test's business; what it pins is that nobody
hand-types a character into a console string that the console cannot render.
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCAN_DIRS = ("core", "skills", "ui")
CONSOLE_ENCODING = "cp1252"


def _encodable(ch: str) -> bool:
    try:
        ch.encode(CONSOLE_ENCODING)
        return True
    except UnicodeEncodeError:
        return False


def _offending(text: str) -> str:
    return "".join(sorted({c for c in text if not _encodable(c)}))


def _print_literals(tree: ast.AST):
    """Every literal string that reaches `print()`, including f-string parts."""
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "print"):
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                yield node.lineno, arg.value
            elif isinstance(arg, ast.JoinedStr):
                for part in arg.values:
                    if isinstance(part, ast.Constant) and isinstance(part.value, str):
                        yield node.lineno, part.value


def _files():
    out = []
    for d in SCAN_DIRS:
        base = ROOT / d
        if base.exists():
            out += [f for f in base.rglob("*.py") if "_archive" not in str(f)]
    out += sorted(ROOT.glob("*.py"))
    return out


def _scan() -> list:
    bad = []
    for f in _files():
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for lineno, text in _print_literals(tree):
            chars = _offending(text)
            if chars:
                # Escaped, never raw: reporting the problem must not reproduce
                # it. The first version of this scan crashed printing its own
                # findings, which was a fair warning.
                bad.append(f"{f.relative_to(ROOT)}:{lineno} "
                           f"[{chars.encode('unicode_escape').decode('ascii')}]")
    return sorted(set(bad))


class TestConsoleStringsAreEncodable:
    def test_no_print_literal_would_crash_a_cp1252_console(self):
        bad = _scan()
        assert not bad, (
            f"{len(bad)} print() site(s) use characters a Windows cp1252 "
            f"console cannot encode, which raises UnicodeEncodeError at the "
            f"moment of printing:\n  " + "\n  ".join(bad) +
            "\n\nUse ASCII in console strings (OK:, ->, --). "
            "See core/tts.py::_clean_for_speech for the same lesson.")

    def test_the_user_facing_harnesses_are_clean(self):
        """Called out separately because a diagnostic that crashes destroys
        the evidence it was gathering — and does it on the success path."""
        for name in ("run_voice_split.py", "run_vision_split.py",
                     "check_split.py", "gen_flags_doc.py", "run_split.py"):
            path = ROOT / name
            if not path.exists():
                continue
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            for lineno, text in _print_literals(tree):
                assert not _offending(text), f"{name}:{lineno}"


class TestTheScannerItself:
    def test_it_detects_a_known_bad_character(self):
        """A guard that cannot fail is decoration."""
        assert _offending("done ✓") == "✓"
        assert _offending("arrow →") == "→"

    def test_it_accepts_ordinary_text_and_cp1252_punctuation(self):
        """Em-dashes and curly quotes ARE in cp1252 — the rule is about what
        the console can render, not about avoiding non-ASCII on principle."""
        assert _offending("plain text") == ""
        assert _offending("an em-dash — and ‘quotes’") == ""

    def test_it_reads_f_string_parts(self):
        tree = ast.parse('print(f"  \\u2713 {x} done")')
        found = [t for _, t in _print_literals(tree)]
        assert any(_offending(t) for t in found)

    def test_it_reports_escaped_never_raw(self):
        """The first version of this scan crashed printing its own findings."""
        chars = _offending("✓")
        rendered = chars.encode("unicode_escape").decode("ascii")
        rendered.encode(CONSOLE_ENCODING)          # must not raise
        assert rendered == "\\u2713"
