"""Jazz chord symbols (Dm7, G7b9) for display. Harte labels stay the internal form."""

from collections.abc import Callable

from jca_core.chords.jazz5 import Jazz5
from jca_core.chords.parts import ChordParts

NO_CHORD_SYMBOL = "N.C."

_STACK = ("9", "11", "13")
_BRACKET_BASES = frozenset({"", "m", "dim", "dim7", "m7b5", "m(maj7)", "sus4", "sus2"})


def chord_symbol(parts: ChordParts) -> str:
    """Return the jazz symbol for a chord, for example "Dm7/C"."""
    if parts.root is None:
        return NO_CHORD_SYMBOL
    suffix = _SUFFIX_BUILDERS[parts.chord_class](parts.extensions)
    slash = f"/{parts.bass}" if parts.bass and parts.bass != parts.root else ""
    return f"{parts.root}{suffix}{slash}"


def _without(extensions: tuple[str, ...], *names: str) -> tuple[str, ...]:
    return tuple(name for name in extensions if name not in names)


def _join(base: str, rest: tuple[str, ...]) -> str:
    """Add the remaining extensions. A base with no number takes them in brackets."""
    if not rest:
        return base
    if base == "" and rest == ("#5",):
        return "+"
    if base in _BRACKET_BASES:
        return f"{base}({','.join(rest)})"
    return base + "".join(rest)


def _stack(extensions: tuple[str, ...], seventh: str) -> tuple[str, tuple[str, ...]]:
    """Return the top of the stack ("7", "9", "11", "13") and the extensions it leaves."""
    present = tuple(name for name in _STACK if name in extensions)
    if not present:
        return "7", _without(extensions, seventh)
    top = present[-1]
    covered = _STACK[: _STACK.index(top) + 1]
    return top, _without(extensions, seventh, *covered)


def _major(extensions: tuple[str, ...]) -> str:
    if "7" in extensions:
        top, rest = _stack(extensions, "7")
        return _join(f"maj{top}", rest)
    if "6" in extensions:
        base = "69" if "9" in extensions else "6"
        return _join(base, _without(extensions, "6", "9"))
    if "9" in extensions:
        return _join("add9", _without(extensions, "9"))
    return _join("", extensions)


def _minor(extensions: tuple[str, ...]) -> str:
    if "b7" in extensions:
        top, rest = _stack(extensions, "b7")
        return _join(f"m{top}", rest)
    if "7" in extensions:
        return _join("m(maj7)", _without(extensions, "7"))
    if "6" in extensions:
        base = "m69" if "9" in extensions else "m6"
        return _join(base, _without(extensions, "6", "9"))
    return _join("m", extensions)


def _dominant(extensions: tuple[str, ...]) -> str:
    top, rest = _stack(extensions, "b7")
    if "4" in rest:
        return _join(f"{top}sus4", _without(rest, "4"))
    return _join(top, rest)


def _half_diminished(extensions: tuple[str, ...]) -> str:
    return _join("m7b5", extensions)


def _diminished(extensions: tuple[str, ...]) -> str:
    if "bb7" in extensions:
        return _join("dim7", _without(extensions, "bb7"))
    return _join("dim", extensions)


def _no_class(extensions: tuple[str, ...]) -> str:
    rest = _without(extensions, "5")
    if "4" in rest:
        return _join("sus4", _without(rest, "4"))
    if "2" in rest:
        return _join("sus2", _without(rest, "2"))
    if "5" in extensions and not rest:
        return "5"
    return _join("", rest)


_SUFFIX_BUILDERS: dict[Jazz5 | None, Callable[[tuple[str, ...]], str]] = {
    Jazz5.MAJ: _major,
    Jazz5.MIN: _minor,
    Jazz5.DOM7: _dominant,
    Jazz5.HDIM7: _half_diminished,
    Jazz5.DIM: _diminished,
    None: _no_class,
}
