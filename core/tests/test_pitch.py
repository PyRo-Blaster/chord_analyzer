import pytest

from jca_core.pitch import pitch_class_name, pitch_class_number, spelling_of


@pytest.mark.parametrize(
    ("name", "number"),
    [
        ("C", 0),
        ("C#", 1),
        ("Db", 1),
        ("E", 4),
        ("F#", 6),
        ("Bb", 10),
        ("B", 11),
        ("Cb", 11),
        ("B#", 0),
    ],
)
def test_pitch_class_number(name, number):
    assert pitch_class_number(name) == number


@pytest.mark.parametrize("name", ["", "H", "c", "sharp", "C♯"])
def test_pitch_class_number_rejects_invalid_names(name):
    with pytest.raises(ValueError, match="Invalid note name"):
        pitch_class_number(name)


@pytest.mark.parametrize(
    ("number", "spelling", "name"),
    [
        (0, "default", "C"),
        (1, "default", "Db"),
        (6, "default", "F#"),
        (6, "flat", "Gb"),
        (10, "default", "Bb"),
        (10, "sharp", "A#"),
    ],
)
def test_pitch_class_name(number, spelling, name):
    assert pitch_class_name(number, spelling) == name


@pytest.mark.parametrize("number", [-1, 12])
def test_pitch_class_name_rejects_numbers_out_of_range(number):
    with pytest.raises(ValueError, match="0 to 11"):
        pitch_class_name(number)


@pytest.mark.parametrize(
    ("name", "spelling"),
    [("C", "default"), ("B", "default"), ("F#", "sharp"), ("Bb", "flat"), ("Db", "flat")],
)
def test_spelling_of(name, spelling):
    assert spelling_of(name) == spelling
