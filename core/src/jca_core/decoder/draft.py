"""Jazz decoder: two model outputs and the bass check become one draft chart."""

from collections.abc import Sequence
from typing import Literal

from jca_core.chords.agreement import Agreement, agreement_level
from jca_core.chords.harte import ParsedChord, parse_chord
from jca_core.chords.parts import chord_parts
from jca_core.grid.resample import labels_per_beat
from jca_core.grid.snap import snap_segments
from jca_core.pitch import pitch_class_name
from jca_core.schema.records import Beat, ChartRecord, ChordSegment

PrimaryModel = Literal["lv_chordia", "btc"]

# Start values. Phase 2 measures accuracy at each agreement level and replaces them.
BASE_CONFIDENCE = {Agreement.A: 0.8, Agreement.B: 0.7, Agreement.C: 0.4, Agreement.D: 0.2}
EXTENSIONS_CONFIDENCE = {Agreement.A: 0.6, Agreement.B: 0.3, Agreement.C: 0.1, Agreement.D: 0.1}
BASS_MISMATCH_PENALTY = 0.2
NO_CHORDAL_INSTRUMENT_FACTOR = 0.5
REVIEW_LEVELS = frozenset({Agreement.C, Agreement.D})
CONFIDENCE_DECIMALS = 2


def decode(
    beats: Sequence[Beat],
    lv_segments: Sequence[ChordSegment],
    btc_segments: Sequence[ChordSegment],
    bass_pitch_classes: Sequence[int | None],
    *,
    primary: PrimaryModel = "lv_chordia",
    has_chordal_instrument: bool = True,
) -> tuple[ChartRecord, ...]:
    """Return one chart record for each beat."""
    if len(bass_pitch_classes) != len(beats):
        raise ValueError(
            "decode needs one bass pitch class for each beat: "
            f"{len(bass_pitch_classes)} values for {len(beats)} beats"
        )
    lv_labels = labels_per_beat(snap_segments(lv_segments, beats), beats)
    btc_labels = labels_per_beat(snap_segments(btc_segments, beats), beats)
    rows = tuple(zip(beats, lv_labels, btc_labels, bass_pitch_classes, strict=True))
    marked_bars = frozenset(
        beat.bar
        for beat, lv_label, btc_label, bass_pc in rows
        if beat.bar >= 1
        and beat.beat == 1
        and _bass_fits_neither(bass_pc, parse_chord(lv_label), parse_chord(btc_label))
    )
    factor = 1.0 if has_chordal_instrument else NO_CHORDAL_INSTRUMENT_FACTOR
    return tuple(
        _record(beat, lv_label, btc_label, bass_pc, primary, beat.bar in marked_bars, factor)
        for beat, lv_label, btc_label, bass_pc in rows
    )


def _bass_fits_neither(bass_pc: int | None, first: ParsedChord, second: ParsedChord) -> bool:
    """True if the bass note is neither the root nor the slash bass of either label."""
    if bass_pc is None:
        return False
    expected = {
        pitch_class
        for chord in (first, second)
        for pitch_class in (chord.root_pc, chord.bass_pc)
        if pitch_class is not None
    }
    return bool(expected) and bass_pc not in expected


def _record(
    beat: Beat,
    lv_label: str,
    btc_label: str,
    bass_pc: int | None,
    primary: PrimaryModel,
    bar_is_marked: bool,
    factor: float,
) -> ChartRecord:
    lv_chord = parse_chord(lv_label)
    btc_chord = parse_chord(btc_label)
    level = agreement_level(lv_chord, btc_chord)
    penalty = BASS_MISMATCH_PENALTY if bar_is_marked else 0.0
    return ChartRecord(
        bar=beat.bar,
        beat=beat.beat,
        time=beat.time,
        lv_chordia=lv_label,
        btc=btc_label,
        bass_pitch_class=None if bass_pc is None else pitch_class_name(bass_pc),
        agreement=level,
        draft=chord_parts(lv_chord if primary == "lv_chordia" else btc_chord),
        confidence=_confidence(BASE_CONFIDENCE[level], penalty, factor),
        extensions_confidence=_confidence(EXTENSIONS_CONFIDENCE[level], penalty, factor),
        needs_review=level in REVIEW_LEVELS or bar_is_marked,
    )


def _confidence(base: float, penalty: float, factor: float) -> float:
    return round(max(0.0, base - penalty) * factor, CONFIDENCE_DECIMALS)
