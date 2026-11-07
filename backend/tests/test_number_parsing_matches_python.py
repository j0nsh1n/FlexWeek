"""The engine reads integers from text exactly as Python's int() does, with Python's own int() as the
oracle: every code point, then the odd strings (underscores, other-script digits, control characters)."""

from __future__ import annotations

import flexweek_engine  # type: ignore[import-untyped]


def outcome(fn):
    try:
        return ("ok", fn())
    except Exception as exc:
        return (type(exc).__name__, str(exc))


def test_int_parser_matches_python_for_every_code_point():
    def check(chars: list[str]) -> None:
        got = flexweek_engine.int_chars("".join(chars))
        for ch, item in zip(chars, got, strict=True):
            want = outcome(lambda ch=ch: int(ch))
            if want[0] == "ok":
                want = ("ok", str(want[1]))
            assert item == want, (repr(ch), item, want)

    chunk: list[str] = []
    for code_point in range(0x110000):
        if 0xD800 <= code_point <= 0xDFFF:
            continue
        chunk.append(chr(code_point))
        if len(chunk) == 4096:
            check(chunk)
            chunk = []
    if chunk:
        check(chunk)


def test_int_parser_matches_python_on_longer_text():
    for text in ("1_2", "\x1c12", "  8", "'", "\x00", "+3", "1__2", "١٢", "\x1c"):
        got = flexweek_engine.int_text(text)
        want = outcome(lambda text=text: int(text))
        if want[0] == "ok":
            want = ("ok", str(want[1]))
        assert got == want, (repr(text), got, want)
