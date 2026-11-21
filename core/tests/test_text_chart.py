from jca_core.chords.agreement import Agreement
from jca_core.chords.harte import parse_chord
from jca_core.chords.parts import chord_parts
from jca_core.export.text_chart import text_chart
from jca_core.schema.records import ChartRecord


def record(bar: int, beat: int, label: str) -> ChartRecord:
    return ChartRecord(
        bar=bar,
        beat=beat,
        time=0.0,
        lv_chordia=label,
        btc=label,
        bass_pitch_class=None,
        agreement=Agreement.A,
        draft=chord_parts(parse_chord(label)),
        confidence=0.8,
    )


def bar(number: int, *labels: str) -> list[ChartRecord]:
    """One label fills a 4/4 bar. Four labels give one for each beat."""
    per_beat = labels * 4 if len(labels) == 1 else labels
    return [record(number, beat, label) for beat, label in enumerate(per_beat, start=1)]


def test_four_bars_on_each_line():
    labels = ["D:min7", "G:7", "C:maj7", "C:maj7", "F:maj7", "B:hdim7", "E:7", "A:min7"]
    records = [r for number, label in enumerate(labels, start=1) for r in bar(number, label)]
    assert text_chart(records).splitlines() == [
        "| Dm7   | G7    | Cmaj7 | Cmaj7 |",
        "| Fmaj7 | Bm7b5 | E7    | Am7   |",
    ]


def test_two_chords_that_split_a_bar_in_half():
    records = bar(1, "D:min7", "D:min7", "G:7", "G:7") + bar(2, "C:maj7")
    assert text_chart(records) == "| Dm7 G7 | Cmaj7  |\n"


def test_an_uneven_change_shows_held_beats():
    records = bar(1, "C:maj7", "C:maj7", "C:maj7", "G:7")
    assert text_chart(records) == "| Cmaj7 / / G7 |\n"


def test_a_user_edit_replaces_the_draft():
    edit = chord_parts(parse_chord("A:min7"))
    records = [r.model_copy(update={"user_edit": edit}) for r in bar(1, "C:maj")]
    assert text_chart(records) == "| Am7 |\n"


def test_a_pickup_bar_leads_the_first_line():
    records = [record(0, 1, "G:7")] + [r for number in range(1, 6) for r in bar(number, "C:maj")]
    assert text_chart(records).splitlines() == [
        "| G7 | C  | C  | C  | C  |",
        "| C  |",
    ]


def test_no_chord_is_written_as_nc():
    assert text_chart(bar(1, "N")) == "| N.C. |\n"


def test_an_empty_chart_is_an_empty_string():
    assert text_chart([]) == ""
