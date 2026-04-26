from core.normalizer import HinglishNormalizer


def test_lowercases_and_trims():
    n = HinglishNormalizer()
    assert n.clean("  HELLO World  ") == "hello world"


def test_strips_unsafe_punctuation():
    n = HinglishNormalizer()
    assert n.clean("chrome, kholo!") == "chrome kholo"
    assert n.clean("hello? are you there?") == "hello are you there"


def test_preserves_url_chars():
    n = HinglishNormalizer()
    out = n.clean("https://github.com/foo kholo")
    assert "https://github.com/foo" in out


def test_preserves_safe_math_chars():
    """+ - . : / % survive normalization.

    `*` and `×` are dropped — the brain encoder doesn't need them, and the
    EntityExtractor's expression regex runs on RAW text so it sees them anyway.
    """
    n = HinglishNormalizer()
    assert n.clean("12 + 7 - 3.5") == "12 + 7 - 3.5"
    assert n.clean("80% accuracy") == "80% accuracy"


def test_drops_multiplication_chars():
    n = HinglishNormalizer()
    assert n.clean("12 * 3") == "12 3"


def test_collapses_whitespace():
    n = HinglishNormalizer()
    assert n.clean("  hello    world  ") == "hello world"


def test_empty_input():
    n = HinglishNormalizer()
    assert n.clean("") == ""
    assert n.clean(None) == ""


def test_normalize_alias_still_works():
    """`.normalize()` is the legacy name; old tests/UIs may still call it."""
    n = HinglishNormalizer()
    assert n.normalize("Hello") == n.clean("Hello")
