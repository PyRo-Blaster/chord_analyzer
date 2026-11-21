import pytest

from jca_core.separation.plan import (
    ALL_MODELS,
    Capabilities,
    HornModel,
    Instrument,
    StemRequest,
    build_separation_plan,
    has_chordal_instrument,
    normalise_other,
)

TRIO = [Instrument.PIANO, Instrument.DOUBLE_BASS, Instrument.DRUMS]
SAX_MODEL_ONLY = Capabilities(sax_model=True, multi_stem=False, text_prompted=False)
NO_HORN_MODELS = Capabilities(sax_model=False, multi_stem=False, text_prompted=False)
MULTI_STEM_ONLY = Capabilities(sax_model=False, multi_stem=True, text_prompted=False)


def stem(name: str, source: str) -> StemRequest:
    return StemRequest(name=name, source=source)


def test_row_1_piano_bass_drums_run_the_six_stem_model_only():
    plan = build_separation_plan(TRIO, ALL_MODELS)
    assert plan.rhythm_stems == (
        stem("drums", "drums"),
        stem("double bass", "bass"),
        stem("piano", "piano"),
    )
    assert plan.horn_model is HornModel.NONE
    assert plan.horn_stems == ()
    assert plan.experimental_stems == ()
    assert plan.warnings == ()


def test_row_2_one_horn_runs_the_sax_model_and_keeps_its_name():
    plan = build_separation_plan([*TRIO, Instrument.ALTO_SAX], ALL_MODELS)
    assert plan.horn_model is HornModel.SAX
    assert plan.horn_stems == (stem("alto sax", "sax"),)
    assert plan.warnings == ()


def test_row_3_horns_of_two_families_use_the_multi_stem_model():
    plan = build_separation_plan([*TRIO, Instrument.TENOR_SAX, Instrument.TRUMPET], ALL_MODELS)
    assert plan.horn_model is HornModel.MULTI_STEM
    assert plan.horn_stems == (stem("tenor sax", "wind"), stem("trumpet", "brass"))
    assert plan.warnings == ()


def test_row_4_two_horns_of_one_family_share_a_stem_with_a_warning():
    plan = build_separation_plan([*TRIO, Instrument.ALTO_SAX, Instrument.TENOR_SAX], ALL_MODELS)
    assert plan.horn_model is HornModel.SAX
    assert plan.horn_stems == (stem("saxes", "sax"),)
    assert len(plan.warnings) == 1
    assert "alto sax and tenor sax" in plan.warnings[0]
    assert "not reliable" in plan.warnings[0]


def test_row_5_an_instrument_with_no_model_is_offered_as_experimental():
    plan = build_separation_plan([*TRIO, Instrument.VIBRAPHONE], ALL_MODELS)
    assert plan.experimental_stems == (stem("vibraphone", "vibraphone"),)
    assert any("experimental" in warning for warning in plan.warnings)


def test_row_6_unused_six_stem_outputs_go_back_to_the_residue():
    plan = build_separation_plan(TRIO, ALL_MODELS)
    assert plan.folded_into_residue() == ("vocals", "guitar", "other")


def test_guitar_and_vocals_are_kept_when_they_are_named():
    plan = build_separation_plan([*TRIO, Instrument.GUITAR, Instrument.VOCALS], ALL_MODELS)
    assert [request.source for request in plan.rhythm_stems] == [
        "vocals",
        "drums",
        "bass",
        "guitar",
        "piano",
    ]
    assert plan.folded_into_residue() == ("other",)


def test_two_bass_instruments_share_the_bass_stem():
    plan = build_separation_plan([Instrument.DOUBLE_BASS, Instrument.ELECTRIC_BASS], ALL_MODELS)
    assert plan.rhythm_stems == (stem("bass", "bass"),)


def test_one_trumpet_needs_the_multi_stem_model():
    plan = build_separation_plan([*TRIO, Instrument.TRUMPET], ALL_MODELS)
    assert plan.horn_model is HornModel.MULTI_STEM
    assert plan.horn_stems == (stem("trumpet", "brass"),)


def test_two_players_of_one_horn_share_a_section_stem():
    plan = build_separation_plan(
        [*TRIO, Instrument.TRUMPET], ALL_MODELS, horn_counts={Instrument.TRUMPET: 2}
    )
    assert plan.horn_stems == (stem("trumpet section", "brass"),)
    assert "not reliable" in plan.warnings[0]


def test_sax_and_clarinet_share_the_wind_stem():
    plan = build_separation_plan([Instrument.ALTO_SAX, Instrument.CLARINET], ALL_MODELS)
    assert plan.horn_model is HornModel.MULTI_STEM
    assert plan.horn_stems == (stem("winds", "wind"),)


def test_without_the_multi_stem_model_only_the_sax_is_separated():
    plan = build_separation_plan([*TRIO, Instrument.TENOR_SAX, Instrument.TRUMPET], SAX_MODEL_ONLY)
    assert plan.horn_model is HornModel.SAX
    assert plan.horn_stems == (stem("tenor sax", "sax"),)
    assert any("trumpet" in warning and "residue" in warning for warning in plan.warnings)


def test_without_any_horn_model_the_horns_stay_in_the_residue():
    plan = build_separation_plan([*TRIO, Instrument.ALTO_SAX], NO_HORN_MODELS)
    assert plan.horn_model is HornModel.NONE
    assert plan.horn_stems == ()
    assert any("alto sax" in warning and "residue" in warning for warning in plan.warnings)


def test_without_the_sax_model_a_sax_uses_the_wind_stem():
    plan = build_separation_plan([*TRIO, Instrument.ALTO_SAX], MULTI_STEM_ONLY)
    assert plan.horn_model is HornModel.MULTI_STEM
    assert plan.horn_stems == (stem("alto sax", "wind"),)


def test_without_the_text_prompted_separator_other_instruments_stay_in_the_residue():
    plan = build_separation_plan([*TRIO, Instrument.VIBRAPHONE], SAX_MODEL_ONLY, other=["Organ"])
    assert plan.experimental_stems == ()
    assert any("vibraphone and organ" in warning for warning in plan.warnings)


def test_free_text_instruments_are_offered_as_experimental():
    plan = build_separation_plan(TRIO, ALL_MODELS, other=["  Organ ", "organ", ""])
    assert plan.experimental_stems == (stem("organ", "organ"),)


def test_horn_counts_must_be_at_least_one():
    with pytest.raises(ValueError, match="at least 1"):
        build_separation_plan(TRIO, ALL_MODELS, horn_counts={Instrument.TRUMPET: 0})


def test_normalise_other_trims_lowers_and_removes_repeats():
    assert normalise_other(["  Organ ", "organ", "", "Harp"]) == ("organ", "harp")


@pytest.mark.parametrize(
    ("instruments", "expected"),
    [
        (TRIO, True),
        ([Instrument.GUITAR, Instrument.DOUBLE_BASS], True),
        ([Instrument.DOUBLE_BASS, Instrument.DRUMS, Instrument.TENOR_SAX], False),
    ],
)
def test_has_chordal_instrument(instruments, expected):
    assert has_chordal_instrument(instruments) is expected
