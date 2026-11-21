import numpy as np

from jca_core.bass.root import bass_pitch_class_per_beat
from jca_core.chords.agreement import Agreement
from jca_core.decoder.draft import decode
from jca_core.export.json_export import analysis_from_json, analysis_to_json
from jca_core.export.text_chart import text_chart
from jca_core.grid.beats import regular_beat_grid
from jca_core.schema.records import AnalysisDocument, ChordSegment

SAMPLE_RATE = 22050
D2_HZ = 73.42
G2_HZ = 98.00
C2_HZ = 65.41


def tone(frequency: float, seconds: float) -> np.ndarray:
    time = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return 0.5 * np.sin(2 * np.pi * frequency * time)


def seg(start: float, end: float, label: str) -> ChordSegment:
    return ChordSegment(start=start, end=end, label=label)


def test_two_five_one_from_model_outputs_to_both_exports():
    # Four bars of 4/4 at 120 BPM: Dm7 | G7 | Cmaj7 | Cmaj7, with the bass on the roots.
    grid = regular_beat_grid([index * 0.5 for index in range(16)], beats_per_bar=4)
    lv = (seg(0.0, 1.9, "D:min7"), seg(1.9, 4.1, "G:7(b9)"), seg(4.1, 8.0, "C:maj7"))
    btc = (
        seg(0.0, 2.0, "D:min7"),
        seg(2.0, 4.0, "G:7"),
        seg(4.0, 6.0, "C:maj7"),
        seg(6.0, 8.0, "A:min7"),
    )
    bass = np.concatenate([tone(D2_HZ, 2.0), tone(G2_HZ, 2.0), tone(C2_HZ, 4.0)])

    bass_pitch_classes = bass_pitch_class_per_beat(bass, SAMPLE_RATE, grid)
    chart = decode(grid, lv, btc, bass_pitch_classes)

    assert bass_pitch_classes == (2,) * 4 + (7,) * 4 + (0,) * 8
    first_beats = chart[::4]
    assert [record.agreement for record in first_beats] == [
        Agreement.A,
        Agreement.B,
        Agreement.A,
        Agreement.D,
    ]
    assert [record.needs_review for record in first_beats] == [False, False, False, True]
    assert text_chart(chart) == "| Dm7   | G7b9  | Cmaj7 | Cmaj7 |\n"

    document = AnalysisDocument(beats=grid, lv_chordia=lv, btc=btc, chart=chart)
    assert analysis_from_json(analysis_to_json(document)) == document
