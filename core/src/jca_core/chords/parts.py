"""The four-part form of a chord: root, class, extensions, bass."""

from pydantic import Field

from jca_core.chords.harte import ParsedChord
from jca_core.chords.jazz5 import Jazz5, classify, extension_names
from jca_core.pitch import pitch_class_name, spelling_of
from jca_core.schema.base import FrozenModel


class ChordParts(FrozenModel):
    """A chord as the editor shows it. Serialised with the key "class"."""

    root: str | None
    chord_class: Jazz5 | None = Field(alias="class")
    extensions: tuple[str, ...] = ()
    bass: str | None = None


NO_CHORD_PARTS = ChordParts(root=None, chord_class=None)


def chord_parts(parsed: ParsedChord) -> ChordParts:
    """Convert a parsed label into its four parts."""
    if parsed.root is None or parsed.bass_pc is None:
        return NO_CHORD_PARTS
    chord_class = classify(parsed.intervals)
    return ChordParts(
        root=parsed.root,
        chord_class=chord_class,
        extensions=extension_names(parsed.intervals, chord_class),
        bass=_bass_name(parsed.root, parsed.bass_interval, parsed.bass_pc),
    )


def _bass_name(root: str, bass_interval: int | None, bass_pc: int) -> str:
    if bass_interval == 0:
        return root
    return pitch_class_name(bass_pc, spelling_of(root))
