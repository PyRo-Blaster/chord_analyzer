# Phase 1a: Core Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `jca_core`, a tested Python package that holds every piece of logic in the design that needs no model: chord label parsing, the Jazz5 classes, agreement levels, the beat grid, the decoder, the separation plan, the residue, the cache key and the exports.

**Architecture:** One uv project in `core/` with a `src/jca_core` package. Every module is a set of pure functions over frozen value types (frozen dataclasses and frozen pydantic models). Harte labels are parsed by `mir_eval`; audio is handled as numpy arrays only, so this package reads no audio files and loads no model.

**Tech Stack:** Python 3.12, uv, mir_eval 0.8, numpy 2, pydantic 2.11+, pytest, hypothesis, pytest-cov, ruff.

**Roadmap:** `docs/superpowers/plans/2026-11-13-phased-roadmap.md`. **Design:** `Jazz Chord Analyzer — Technical Design.md`.

---

## Conventions for every task

- All commands start from the repository root, `/Users/chenji/Desktop/CodeSpace/chord_analyzer`.
- Tests live flat in `core/tests/`, one file for each module.
- Follow TDD in order: write the test, run it and see it fail, write the code, run it and see it pass, commit.
- Never change an argument in place. Return new tuples, new arrays and new models.
- Commit messages use `<type>: <description>` with no attribution lines.

## Decisions this plan makes where the design is open

Each of these is a choice, not a fact from the design. Change the test first if one is wrong.

| # | Topic | Decision |
| --- | --- | --- |
| 1 | Jazz5 rule | Class comes from the third, fifth and seventh, as the JAAH paper describes. A chord with no third and a minor seventh (7sus4) is dom7. A chord with no third and no minor seventh (sus, power chord) has no class. The JAAH flow chart (Figure 3) is an image and was not read; check the rule against it in Phase 2. |
| 2 | Extensions | Extensions are the tones outside the core tones of the class. Omitted tones are ignored. D:min7 gives `["b7"]`, as in the design's chart record. |
| 3 | "X" label | Treated as no chord, the same as "N". |
| 4 | Snap rule | A chord change moves to the nearest beat. A change exactly half a beat from a bar line moves to the bar line. |
| 5 | Short segments | After snapping, a segment with no length is removed and equal neighbours are merged. |
| 6 | Bass check | The bass pitch class on beat 1 must equal the root or the slash bass of either model. If not, the whole bar is marked. |
| 7 | Confidence | Start values: A 0.8, B 0.7, C 0.4, D 0.2. A failed bass check subtracts 0.2. No piano or guitar multiplies by 0.5. Phase 2 calibrates these. |
| 8 | Chart record | Two fields are added to the design's record: `extensions_confidence` (the design asks for a tier 2 confidence) and `needs_review` (the design asks for bars to be marked). |
| 9 | Bass root method | FFT energy between 40 and 400 Hz, summed by pitch class, with numpy only. Phase 2 measures it against the model roots. |
| 10 | Cache key | Includes the separator name, so that stems from BS-RoFormer and from the Demucs fallback never share a cache entry. |
| 11 | Separation plan | Takes the available models as input, because the 53-stem model will not run on this computer. |
| 12 | Text chart | Four bars on each line, `|` between bars, one chord for a whole bar, two chords for two equal halves, and `/` for a held beat in any other case. |

Not in this plan: the schema records for stems and jobs, and stem export. They need file input and output, so they belong to Phase 1b and Phase 3.

## File structure

```
.gitignore
core/
  pyproject.toml
  .python-version
  src/jca_core/
    __init__.py
    pitch.py                 note names and pitch-class numbers
    schema/base.py           FrozenModel, the base of every record
    schema/records.py        Beat, ChordSegment, ChartRecord, AnalysisDocument
    chords/harte.py          Harte label to ParsedChord
    chords/jazz5.py          Jazz5 class and extension names
    chords/parts.py          ChordParts: root, class, extensions, bass
    chords/agreement.py      agreement level A to D
    chords/display.py        ChordParts to a jazz symbol
    grid/beats.py            beat grid with bar and beat numbers
    grid/snap.py             snap chord changes to the grid
    grid/resample.py         one label for each beat
    bass/root.py             strongest bass pitch class for each beat
    decoder/draft.py         draft chart records
    separation/plan.py       instrument list to separation plan
    separation/residue.py    mix minus stems
    cache/key.py             file hash and stem cache key
    export/text_chart.py     text chart, four bars on each line
    export/json_export.py    analysis document to and from JSON
  tests/
    test_package.py  test_pitch.py  test_base.py  test_harte.py  test_jazz5.py
    test_parts.py  test_agreement.py  test_display.py  test_records.py
    test_beats.py  test_snap.py  test_resample.py  test_bass_root.py
    test_draft.py  test_plan.py  test_residue.py  test_cache_key.py
    test_text_chart.py  test_json_export.py  test_end_to_end.py
```

---

### Task 1: Repository and project scaffold

**Files:**
- Create: `.gitignore`
- Create: `core/pyproject.toml`
- Create: `core/.python-version`
- Create: `core/src/jca_core/__init__.py` and one empty `__init__.py` in each subpackage
- Test: `core/tests/test_package.py`

- [ ] **Step 1: Start the repository**

Run:

```bash
git init
```

Expected: `Initialized empty Git repository in /Users/chenji/Desktop/CodeSpace/chord_analyzer/.git/`

- [ ] **Step 2: Write the ignore file**

Create `.gitignore`:

```text
# Real audio and pipeline output never go into the repository
data/
runs/

# Python
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
.hypothesis/
.ruff_cache/
.coverage
htmlcov/

# Node
node_modules/

# macOS
.DS_Store
```

- [ ] **Step 3: Commit the design and the plans**

```bash
git add .gitignore "Jazz Chord Analyzer — Technical Design.md" docs
git commit -m "chore: start repository with design and plans"
```

- [ ] **Step 4: Write the project file**

Create `core/pyproject.toml`:

```toml
[project]
name = "jca-core"
version = "0.1.0"
description = "Model-free logic for the Jazz Chord Analyzer"
requires-python = ">=3.12"
dependencies = [
    "mir_eval>=0.8",
    "numpy>=2.0",
    "pydantic>=2.11",
]

[dependency-groups]
dev = [
    "hypothesis>=6.100",
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.6",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/jca_core"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-markers"

[tool.coverage.run]
source = ["jca_core"]
branch = true

[tool.coverage.report]
fail_under = 80
show_missing = true

[tool.ruff]
line-length = 100
target-version = "py312"
```

Create `core/.python-version`:

```text
3.12
```

- [ ] **Step 5: Create the package folders**

```bash
mkdir -p core/tests core/src/jca_core/{schema,chords,grid,bass,decoder,separation,cache,export}
touch core/src/jca_core/__init__.py core/src/jca_core/{schema,chords,grid,bass,decoder,separation,cache,export}/__init__.py
```

- [ ] **Step 6: Write the first test**

Create `core/tests/test_package.py`:

```python
import jca_core


def test_package_imports():
    assert jca_core.__name__ == "jca_core"
```

- [ ] **Step 7: Install and run**

```bash
uv sync --directory core
uv run --directory core pytest -v
```

Expected: `1 passed`. `uv sync` also writes `core/uv.lock`.

- [ ] **Step 8: Commit**

```bash
git add core/pyproject.toml core/.python-version core/uv.lock core/src core/tests
git commit -m "chore: scaffold the jca_core package"
```

---

### Task 2: Pitch-class names and numbers

**Files:**
- Create: `core/src/jca_core/pitch.py`
- Test: `core/tests/test_pitch.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_pitch.py`:

```python
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
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_pitch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.pitch'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/pitch.py`:

```python
"""Note names and pitch-class numbers (C is 0, B is 11)."""

import re
from typing import Literal

PITCH_CLASS_COUNT = 12

Spelling = Literal["default", "sharp", "flat"]

_NATURALS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NOTE_PATTERN = re.compile(r"[A-G][#b]*")
_NAMES: dict[str, tuple[str, ...]] = {
    "default": ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"),
    "sharp": ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"),
    "flat": ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"),
}


def pitch_class_number(name: str) -> int:
    """Return 0 to 11 for a note name such as "C", "F#" or "Bb"."""
    if not _NOTE_PATTERN.fullmatch(name):
        raise ValueError(f"Invalid note name: {name!r}")
    return (_NATURALS[name[0]] + name.count("#") - name.count("b")) % PITCH_CLASS_COUNT


def pitch_class_name(number: int, spelling: Spelling = "default") -> str:
    """Return the note name for a pitch-class number."""
    if not 0 <= number < PITCH_CLASS_COUNT:
        raise ValueError(f"Pitch class must be 0 to 11, got {number}")
    return _NAMES[spelling][number]


def spelling_of(name: str) -> Spelling:
    """Return the spelling family of a note name, so that related notes match it."""
    if "#" in name:
        return "sharp"
    if "b" in name:
        return "flat"
    return "default"
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_pitch.py -v`
Expected: PASS (27 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/pitch.py core/tests/test_pitch.py
git commit -m "feat: add pitch-class names and numbers"
```

---

### Task 3: FrozenModel base

**Files:**
- Create: `core/src/jca_core/schema/base.py`
- Test: `core/tests/test_base.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_base.py`:

```python
import pytest
from pydantic import Field, ValidationError

from jca_core.schema.base import FrozenModel


class Sample(FrozenModel):
    plain: int
    renamed: int = Field(alias="class")


def test_fields_cannot_be_reassigned():
    sample = Sample(plain=1, renamed=2)
    with pytest.raises(ValidationError):
        sample.plain = 5


def test_serialises_with_the_alias():
    assert Sample(plain=1, renamed=2).model_dump() == {"plain": 1, "class": 2}


def test_accepts_the_field_name_and_the_alias():
    assert Sample(plain=1, renamed=2) == Sample.model_validate({"plain": 1, "class": 2})


def test_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Sample.model_validate({"plain": 1, "class": 2, "extra": 3})
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.schema.base'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/schema/base.py`:

```python
"""Base class for every record in the system."""

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """An immutable record that fails fast on unknown fields."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_base.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/schema/base.py core/tests/test_base.py
git commit -m "feat: add the frozen record base class"
```

---

### Task 4: Harte label parser

**Files:**
- Create: `core/src/jca_core/chords/harte.py`
- Test: `core/tests/test_harte.py`

The parser wraps `mir_eval.chord.encode`. Note the argument `reduce_extended_chords=True`: in mir_eval this is what keeps the 9th, 11th and 13th, folded into one octave. With `False` they are dropped.

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_harte.py`:

```python
import dataclasses

import pytest

from jca_core.chords.harte import InvalidChordLabelError, parse_chord


@pytest.mark.parametrize(
    ("label", "root", "root_pc", "intervals", "bass_interval"),
    [
        ("C:maj", "C", 0, {0, 4, 7}, 0),
        ("C", "C", 0, {0, 4, 7}, 0),
        ("A#", "A#", 10, {0, 4, 7}, 0),
        ("D:min7", "D", 2, {0, 3, 7, 10}, 0),
        ("C:7(b9)", "C", 0, {0, 1, 4, 7, 10}, 0),
        ("C:9", "C", 0, {0, 2, 4, 7, 10}, 0),
        ("C:13", "C", 0, {0, 2, 4, 5, 7, 9, 10}, 0),
        ("C:maj7(#11)", "C", 0, {0, 4, 6, 7, 11}, 0),
        ("C:sus4", "C", 0, {0, 5, 7}, 0),
        ("C:hdim7", "C", 0, {0, 3, 6, 10}, 0),
        ("C:dim7", "C", 0, {0, 3, 6, 9}, 0),
        ("C:7(*5)", "C", 0, {0, 4, 10}, 0),
        ("C:maj/3", "C", 0, {0, 4, 7}, 4),
        ("D:min7/b7", "D", 2, {0, 3, 7, 10}, 10),
        ("Bb:maj6", "Bb", 10, {0, 4, 7, 9}, 0),
        ("F#:minmaj7", "F#", 6, {0, 3, 7, 11}, 0),
    ],
)
def test_parse_chord(label, root, root_pc, intervals, bass_interval):
    parsed = parse_chord(label)
    assert parsed.label == label
    assert parsed.root == root
    assert parsed.root_pc == root_pc
    assert parsed.intervals == frozenset(intervals)
    assert parsed.bass_interval == bass_interval
    assert not parsed.is_no_chord


@pytest.mark.parametrize("label", ["N", "X"])
def test_no_chord_and_unknown_have_no_root(label):
    parsed = parse_chord(label)
    assert parsed.is_no_chord
    assert parsed.root is None
    assert parsed.root_pc is None
    assert parsed.intervals == frozenset()
    assert parsed.bass_interval is None
    assert parsed.bass_pc is None


@pytest.mark.parametrize(
    ("label", "bass_pc"),
    [("D:min7", 2), ("D:min7/b7", 0), ("C:maj/3", 4), ("Bb:maj/5", 5)],
)
def test_bass_pc_is_an_absolute_pitch_class(label, bass_pc):
    assert parse_chord(label).bass_pc == bass_pc


@pytest.mark.parametrize("label", ["", "H:maj", "C:foo", "c:maj", "C:b9"])
def test_invalid_labels_raise(label):
    with pytest.raises(InvalidChordLabelError, match="Invalid chord label"):
        parse_chord(label)


def test_parsed_chord_is_immutable():
    parsed = parse_chord("C:maj")
    with pytest.raises(dataclasses.FrozenInstanceError):
        parsed.root = "D"
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_harte.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.chords.harte'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/chords/harte.py`:

```python
"""Parse Harte chord labels (for example "D:min7/b7") with mir_eval."""

from dataclasses import dataclass
from functools import lru_cache

import mir_eval.chord

from jca_core.pitch import PITCH_CLASS_COUNT

NO_CHORD = "N"
PARSE_CACHE_SIZE = 4096


class InvalidChordLabelError(ValueError):
    """A label is not valid Harte notation."""


@dataclass(frozen=True)
class ParsedChord:
    """A chord label split into numbers.

    intervals: semitones above the root, in one octave, including 0 for the root.
    bass_interval: semitones from the root up to the bass note (0 in root position).
    A no-chord label ("N" or "X") has no root, no intervals and no bass.
    """

    label: str
    root: str | None
    root_pc: int | None
    intervals: frozenset[int]
    bass_interval: int | None

    @property
    def is_no_chord(self) -> bool:
        return self.root_pc is None

    @property
    def bass_pc(self) -> int | None:
        if self.root_pc is None or self.bass_interval is None:
            return None
        return (self.root_pc + self.bass_interval) % PITCH_CLASS_COUNT


@lru_cache(maxsize=PARSE_CACHE_SIZE)
def parse_chord(label: str) -> ParsedChord:
    """Parse one Harte label. Raises InvalidChordLabelError for a bad label."""
    try:
        root_number, bitmap, bass_number = mir_eval.chord.encode(
            label, reduce_extended_chords=True
        )
        root_name = mir_eval.chord.split(label, reduce_extended_chords=True)[0]
    except mir_eval.chord.InvalidChordException as error:
        raise InvalidChordLabelError(f"Invalid chord label: {label!r}") from error
    if root_number < 0:
        return ParsedChord(
            label=label, root=None, root_pc=None, intervals=frozenset(), bass_interval=None
        )
    return ParsedChord(
        label=label,
        root=root_name,
        root_pc=int(root_number),
        intervals=frozenset(index for index, present in enumerate(bitmap) if present),
        bass_interval=int(bass_number),
    )
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_harte.py -v`
Expected: PASS (28 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/chords/harte.py core/tests/test_harte.py
git commit -m "feat: parse Harte chord labels"
```

---

### Task 5: Jazz5 class and extension names

**Files:**
- Create: `core/src/jca_core/chords/jazz5.py`
- Test: `core/tests/test_jazz5.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_jazz5.py`:

```python
import pytest

from jca_core.chords.harte import parse_chord
from jca_core.chords.jazz5 import Jazz5, classify, extension_intervals, extension_names


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("C:maj", Jazz5.MAJ),
        ("C:maj7", Jazz5.MAJ),
        ("C:maj6", Jazz5.MAJ),
        ("C:maj9", Jazz5.MAJ),
        ("C:aug", Jazz5.MAJ),
        ("C:min", Jazz5.MIN),
        ("C:min7", Jazz5.MIN),
        ("C:min6", Jazz5.MIN),
        ("C:minmaj7", Jazz5.MIN),
        ("C:min11", Jazz5.MIN),
        ("C:min7(*5)", Jazz5.MIN),
        ("C:7", Jazz5.DOM7),
        ("C:9", Jazz5.DOM7),
        ("C:13", Jazz5.DOM7),
        ("C:7(b9)", Jazz5.DOM7),
        ("C:7(#9)", Jazz5.DOM7),
        ("C:7(*5)", Jazz5.DOM7),
        ("C:sus4(b7)", Jazz5.DOM7),
        ("C:hdim7", Jazz5.HDIM7),
        ("C:dim", Jazz5.DIM),
        ("C:dim7", Jazz5.DIM),
        ("C:sus4", None),
        ("C:sus2", None),
        ("C:5", None),
        ("C:1", None),
    ],
)
def test_classify(label, expected):
    assert classify(parse_chord(label).intervals) is expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("C:maj", ()),
        ("C:maj7", ("7",)),
        ("C:maj6", ("6",)),
        ("C:maj9", ("7", "9")),
        ("C:maj7(#11)", ("7", "#11")),
        ("C:maj7(*5,b5)", ("b5", "7")),
        ("C:aug", ("#5",)),
        ("D:min7", ("b7",)),
        ("C:min6", ("6",)),
        ("C:minmaj7", ("7",)),
        ("C:min11", ("b7", "9", "11")),
        ("C:7", ()),
        ("C:7(b9)", ("b9",)),
        ("C:7(#9)", ("#9",)),
        ("C:13", ("9", "11", "13")),
        ("C:7(b13)", ("b13",)),
        ("C:7(*5,b13)", ("#5",)),
        ("C:hdim7", ()),
        ("C:dim7", ("bb7",)),
        ("C:sus4", ("4", "5")),
        ("C:sus2", ("2", "5")),
        ("C:sus4(b7)", ("4",)),
        ("C:sus4(b7,9)", ("4", "9")),
    ],
)
def test_extension_names(label, expected):
    intervals = parse_chord(label).intervals
    assert extension_names(intervals, classify(intervals)) == expected


def test_extension_intervals_are_the_tones_outside_the_core():
    ninth = parse_chord("C:9").intervals
    assert extension_intervals(ninth, Jazz5.DOM7) == frozenset({2})


def test_extension_intervals_without_a_class_keep_everything_but_the_root():
    sus = parse_chord("C:sus4").intervals
    assert extension_intervals(sus, None) == frozenset({5, 7})


def test_omitted_tones_are_not_extensions():
    no_fifth = parse_chord("C:7(*5)").intervals
    assert extension_intervals(no_fifth, Jazz5.DOM7) == frozenset()
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_jazz5.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.chords.jazz5'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/chords/jazz5.py`:

```python
"""The five jazz chord classes of the JAAH paper, and names for the tones outside them."""

from enum import StrEnum

ROOT = 0
MINOR_THIRD = 3
MAJOR_THIRD = 4
DIMINISHED_FIFTH = 6
PERFECT_FIFTH = 7
MINOR_SEVENTH = 10
MAJOR_SEVENTH = 11


class Jazz5(StrEnum):
    MAJ = "maj"
    MIN = "min"
    DOM7 = "dom7"
    HDIM7 = "hdim7"
    DIM = "dim"


CORE_INTERVALS: dict[Jazz5, frozenset[int]] = {
    Jazz5.MAJ: frozenset({ROOT, MAJOR_THIRD, PERFECT_FIFTH}),
    Jazz5.MIN: frozenset({ROOT, MINOR_THIRD, PERFECT_FIFTH}),
    Jazz5.DOM7: frozenset({ROOT, MAJOR_THIRD, PERFECT_FIFTH, MINOR_SEVENTH}),
    Jazz5.HDIM7: frozenset({ROOT, MINOR_THIRD, DIMINISHED_FIFTH, MINOR_SEVENTH}),
    Jazz5.DIM: frozenset({ROOT, MINOR_THIRD, DIMINISHED_FIFTH}),
}

_PLAIN_NAMES = {
    1: "b9",
    2: "9",
    3: "#9",
    4: "3",
    5: "11",
    6: "#11",
    7: "5",
    8: "b13",
    9: "13",
    10: "b7",
    11: "7",
}
_NAME_ORDER = (
    "2", "3", "4", "b5", "5", "#5", "6", "bb7", "b7", "7",
    "b9", "9", "#9", "11", "#11", "b13", "13",
)  # fmt: skip


def classify(intervals: frozenset[int]) -> Jazz5 | None:
    """Return the Jazz5 class, or None for a chord that fits no class (sus, power chord)."""
    has_major_third = MAJOR_THIRD in intervals
    has_minor_seventh = MINOR_SEVENTH in intervals
    if MINOR_THIRD in intervals and not has_major_third:
        if DIMINISHED_FIFTH in intervals and PERFECT_FIFTH not in intervals:
            return Jazz5.HDIM7 if has_minor_seventh else Jazz5.DIM
        return Jazz5.MIN
    if has_major_third:
        return Jazz5.DOM7 if has_minor_seventh else Jazz5.MAJ
    return Jazz5.DOM7 if has_minor_seventh else None


def extension_intervals(intervals: frozenset[int], chord_class: Jazz5 | None) -> frozenset[int]:
    """Return the tones that are not core tones of the class."""
    core = CORE_INTERVALS[chord_class] if chord_class is not None else frozenset({ROOT})
    return intervals - core


def extension_names(intervals: frozenset[int], chord_class: Jazz5 | None) -> tuple[str, ...]:
    """Return the extension tones as degree names, in a fixed order."""
    names = {
        _extension_name(semitone, intervals, chord_class)
        for semitone in extension_intervals(intervals, chord_class)
    }
    return tuple(name for name in _NAME_ORDER if name in names)


def _extension_name(semitone: int, intervals: frozenset[int], chord_class: Jazz5 | None) -> str:
    has_third = bool(intervals & {MINOR_THIRD, MAJOR_THIRD})
    has_seventh = bool(intervals & {MINOR_SEVENTH, MAJOR_SEVENTH})
    has_fifth = PERFECT_FIFTH in intervals
    if semitone == 2 and not has_third and not has_seventh:
        return "2"
    if semitone == 5 and not has_third:
        return "4"
    if semitone == 6 and not has_fifth:
        return "b5"
    if semitone == 8 and not has_fifth:
        return "#5"
    if semitone == 9 and chord_class is Jazz5.DIM:
        return "bb7"
    if semitone == 9 and not has_seventh:
        return "6"
    return _PLAIN_NAMES[semitone]
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_jazz5.py -v`
Expected: PASS (51 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/chords/jazz5.py core/tests/test_jazz5.py
git commit -m "feat: classify chords into the Jazz5 classes"
```

---

### Task 6: Chord parts

**Files:**
- Create: `core/src/jca_core/chords/parts.py`
- Test: `core/tests/test_parts.py`

`ChordParts` is the four-part form of the design: root, class, extensions, bass. It is the type of `draft` and `user_edit` in the chart record.

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_parts.py`:

```python
import pytest
from pydantic import ValidationError

from jca_core.chords.harte import parse_chord
from jca_core.chords.jazz5 import Jazz5
from jca_core.chords.parts import NO_CHORD_PARTS, ChordParts, chord_parts


def test_matches_the_chart_record_in_the_design():
    parts = chord_parts(parse_chord("D:min7"))
    assert parts.model_dump(mode="json") == {
        "root": "D",
        "class": "min",
        "extensions": ["b7"],
        "bass": "D",
    }


@pytest.mark.parametrize(
    ("label", "bass"),
    [
        ("C:maj/3", "E"),
        ("D:min7/b7", "C"),
        ("Bb:maj/5", "F"),
        ("Eb:maj/3", "G"),
        ("Db:maj/5", "Ab"),
        ("F#:maj/3", "A#"),
    ],
)
def test_slash_bass_is_named_in_the_spelling_of_the_root(label, bass):
    assert chord_parts(parse_chord(label)).bass == bass


@pytest.mark.parametrize("label", ["N", "X"])
def test_no_chord_has_empty_parts(label):
    assert chord_parts(parse_chord(label)) == NO_CHORD_PARTS
    assert NO_CHORD_PARTS.model_dump(mode="json") == {
        "root": None,
        "class": None,
        "extensions": [],
        "bass": None,
    }


def test_chord_without_a_class():
    parts = chord_parts(parse_chord("G:sus4"))
    assert parts.chord_class is None
    assert parts.extensions == ("4", "5")


def test_accepts_the_field_name_and_the_alias():
    by_name = ChordParts(root="C", chord_class=Jazz5.MAJ)
    by_alias = ChordParts.model_validate({"root": "C", "class": "maj"})
    assert by_name == by_alias


def test_parts_are_immutable():
    parts = chord_parts(parse_chord("C:maj"))
    with pytest.raises(ValidationError):
        parts.root = "D"
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_parts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.chords.parts'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/chords/parts.py`:

```python
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
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_parts.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/chords/parts.py core/tests/test_parts.py
git commit -m "feat: split chords into root, class, extensions and bass"
```

---

### Task 7: Agreement level

**Files:**
- Create: `core/src/jca_core/chords/agreement.py`
- Test: `core/tests/test_agreement.py`

The four parametrised groups are the four rows of the agreement table in the design.

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_agreement.py`:

```python
import pytest

from jca_core.chords.agreement import Agreement, agreement_level
from jca_core.chords.harte import parse_chord


def level(first: str, second: str) -> Agreement:
    return agreement_level(parse_chord(first), parse_chord(second))


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("D:min7", "D:min7"),
        ("C#:maj", "Db:maj"),
        ("C:maj/3", "C:maj"),
        ("C:7(*5)", "C:7"),
        ("N", "N"),
        ("N", "X"),
    ],
)
def test_level_a_same_root_class_and_extensions(first, second):
    assert level(first, second) is Agreement.A


@pytest.mark.parametrize(
    ("first", "second"),
    [("C:9", "C:7"), ("C:maj7", "C:maj"), ("D:min7", "D:min"), ("G:7(b9)", "G:7")],
)
def test_level_b_same_root_and_class_different_extensions(first, second):
    assert level(first, second) is Agreement.B


@pytest.mark.parametrize(
    ("first", "second"),
    [("C:maj7", "C:7"), ("C:min7", "C:maj"), ("B:hdim7", "B:dim"), ("C:sus4", "C:maj")],
)
def test_level_c_same_root_different_class(first, second):
    assert level(first, second) is Agreement.C


@pytest.mark.parametrize(
    ("first", "second"),
    [("C:maj", "G:maj"), ("A:min7", "C:maj6"), ("C:maj", "N"), ("N", "C:maj")],
)
def test_level_d_different_root(first, second):
    assert level(first, second) is Agreement.D


def test_agreement_does_not_depend_on_the_order():
    assert level("C:9", "C:7") is level("C:7", "C:9")
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_agreement.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.chords.agreement'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/chords/agreement.py`:

```python
"""Agreement level between the labels of two chord models."""

from enum import StrEnum

from jca_core.chords.harte import ParsedChord
from jca_core.chords.jazz5 import classify, extension_intervals


class Agreement(StrEnum):
    A = "A"  # same root, same class, same extensions
    B = "B"  # same root and class, different extensions
    C = "C"  # same root, different class
    D = "D"  # different root


def agreement_level(first: ParsedChord, second: ParsedChord) -> Agreement:
    """Compare two labels. The bass note is ignored, and two no-chord labels agree."""
    if first.root_pc != second.root_pc:
        return Agreement.D
    first_class = classify(first.intervals)
    second_class = classify(second.intervals)
    if first_class != second_class:
        return Agreement.C
    first_extensions = extension_intervals(first.intervals, first_class)
    second_extensions = extension_intervals(second.intervals, second_class)
    return Agreement.A if first_extensions == second_extensions else Agreement.B
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_agreement.py -v`
Expected: PASS (19 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/chords/agreement.py core/tests/test_agreement.py
git commit -m "feat: compute the agreement level of two chord labels"
```

---

### Task 8: Jazz chord symbols

**Files:**
- Create: `core/src/jca_core/chords/display.py`
- Test: `core/tests/test_display.py`

The symbol is built from `ChordParts`, not from the Harte label, because a user edit has parts and no label.

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_display.py`:

```python
import pytest

from jca_core.chords.display import chord_symbol
from jca_core.chords.harte import parse_chord
from jca_core.chords.jazz5 import Jazz5
from jca_core.chords.parts import ChordParts, chord_parts


@pytest.mark.parametrize(
    ("label", "symbol"),
    [
        ("C:maj", "C"),
        ("C", "C"),
        ("C:maj7", "Cmaj7"),
        ("C:maj9", "Cmaj9"),
        ("C:maj6", "C6"),
        ("C:maj(9)", "Cadd9"),
        ("C:maj7(#11)", "Cmaj7#11"),
        ("C:maj(#11)", "C(#11)"),
        ("C:aug", "C+"),
        ("C:min", "Cm"),
        ("D:min7", "Dm7"),
        ("C:min9", "Cm9"),
        ("C:min11", "Cm11"),
        ("C:min6", "Cm6"),
        ("F#:minmaj7", "F#m(maj7)"),
        ("G:7", "G7"),
        ("G:7(b9)", "G7b9"),
        ("C:7(#9)", "C7#9"),
        ("Db:7(b13)", "Db7b13"),
        ("C:9", "C9"),
        ("C:13", "C13"),
        ("C:sus4(b7)", "C7sus4"),
        ("C:sus4(b7,9)", "C9sus4"),
        ("B:hdim7", "Bm7b5"),
        ("C:dim", "Cdim"),
        ("C:dim7", "Cdim7"),
        ("C:sus4", "Csus4"),
        ("C:sus2", "Csus2"),
        ("C:5", "C5"),
        ("C:1", "C"),
        ("C:maj/3", "C/E"),
        ("D:min7/b7", "Dm7/C"),
        ("Bb:maj/5", "Bb/F"),
        ("N", "N.C."),
        ("X", "N.C."),
    ],
)
def test_chord_symbol_from_a_label(label, symbol):
    assert chord_symbol(chord_parts(parse_chord(label))) == symbol


def test_chord_symbol_from_edited_parts():
    edited = ChordParts(root="G", chord_class=Jazz5.DOM7, extensions=("b9", "13"), bass="G")
    assert chord_symbol(edited) == "G13b9"


def test_additions_to_a_plain_triad_go_in_brackets():
    edited = ChordParts(root="C", chord_class=Jazz5.MIN, extensions=("11",))
    assert chord_symbol(edited) == "Cm(11)"
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_display.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.chords.display'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/chords/display.py`:

```python
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
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_display.py -v`
Expected: PASS (37 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/chords/display.py core/tests/test_display.py
git commit -m "feat: render chords as jazz symbols"
```

---

### Task 9: Schema records

**Files:**
- Create: `core/src/jca_core/schema/records.py`
- Test: `core/tests/test_records.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_records.py`:

```python
import pytest
from pydantic import ValidationError

from jca_core.schema.records import (
    SCHEMA_VERSION,
    AnalysisDocument,
    Beat,
    ChartRecord,
    ChordSegment,
)

DESIGN_EXAMPLE = {
    "bar": 9,
    "beat": 1,
    "time": 14.62,
    "lv_chordia": "D:min7",
    "btc": "D:min7",
    "bass_pitch_class": "D",
    "agreement": "A",
    "draft": {"root": "D", "class": "min", "extensions": ["b7"], "bass": "D"},
    "confidence": 0.8,
    "user_edit": None,
}


def test_the_chart_record_of_the_design_validates_and_round_trips():
    record = ChartRecord.model_validate(DESIGN_EXAMPLE)
    dumped = record.model_dump(mode="json")
    assert {key: dumped[key] for key in DESIGN_EXAMPLE} == DESIGN_EXAMPLE
    assert dumped["extensions_confidence"] == 0.0
    assert dumped["needs_review"] is False


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_confidence_must_be_between_zero_and_one(confidence):
    with pytest.raises(ValidationError):
        ChartRecord.model_validate({**DESIGN_EXAMPLE, "confidence": confidence})


def test_agreement_must_be_a_known_level():
    with pytest.raises(ValidationError):
        ChartRecord.model_validate({**DESIGN_EXAMPLE, "agreement": "E"})


def test_segment_end_must_not_be_before_start():
    with pytest.raises(ValidationError, match="end must not be before start"):
        ChordSegment(start=2.0, end=1.0, label="C:maj")


def test_segment_label_must_not_be_empty():
    with pytest.raises(ValidationError):
        ChordSegment(start=0.0, end=1.0, label="")


@pytest.mark.parametrize("fields", [{"bar": -1}, {"beat": 0}, {"time": -0.5}])
def test_beat_rejects_impossible_numbers(fields):
    with pytest.raises(ValidationError):
        Beat(**{"time": 0.0, "bar": 1, "beat": 1, **fields})


def test_analysis_document_carries_a_schema_version():
    document = AnalysisDocument(beats=(), lv_chordia=(), btc=(), chart=())
    assert document.schema_version == SCHEMA_VERSION == 1


def test_records_are_immutable():
    beat = Beat(time=0.0, bar=1, beat=1)
    with pytest.raises(ValidationError):
        beat.time = 1.0
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_records.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.schema.records'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/schema/records.py`:

```python
"""Records that move between the pipeline stages, the API and the exports."""

from typing import Self

from pydantic import Field, model_validator

from jca_core.chords.agreement import Agreement
from jca_core.chords.parts import ChordParts
from jca_core.schema.base import FrozenModel

SCHEMA_VERSION = 1


class Beat(FrozenModel):
    """One beat of the grid. Bar 0 holds pickup beats before the first downbeat."""

    time: float = Field(ge=0)
    bar: int = Field(ge=0)
    beat: int = Field(ge=1)


class ChordSegment(FrozenModel):
    """One chord from a model: a Harte label over a time range in seconds."""

    start: float = Field(ge=0)
    end: float
    label: str = Field(min_length=1)

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        if self.end < self.start:
            raise ValueError("end must not be before start")
        return self


class ChartRecord(FrozenModel):
    """The chart record of the design, one for each beat."""

    bar: int = Field(ge=0)
    beat: int = Field(ge=1)
    time: float = Field(ge=0)
    lv_chordia: str
    btc: str
    bass_pitch_class: str | None
    agreement: Agreement
    draft: ChordParts
    confidence: float = Field(ge=0, le=1)
    extensions_confidence: float = Field(default=0.0, ge=0, le=1)
    needs_review: bool = False
    user_edit: ChordParts | None = None


class AnalysisDocument(FrozenModel):
    """Everything the JSON export holds: grid, both model outputs, chart with edits."""

    schema_version: int = SCHEMA_VERSION
    beats: tuple[Beat, ...]
    lv_chordia: tuple[ChordSegment, ...]
    btc: tuple[ChordSegment, ...]
    chart: tuple[ChartRecord, ...]
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_records.py -v`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/schema/records.py core/tests/test_records.py
git commit -m "feat: add beat, segment, chart and analysis records"
```

---

### Task 10: Beat grid

**Files:**
- Create: `core/src/jca_core/grid/beats.py`
- Test: `core/tests/test_beats.py`

Two ways to number the beats: from the downbeats of a tracker, or from a time signature and a first downbeat that the user sets.

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_beats.py`:

```python
import pytest

from jca_core.grid.beats import beat_boundaries, build_beat_grid, regular_beat_grid


def numbers(grid):
    return [(beat.bar, beat.beat) for beat in grid]


def test_regular_grid_numbers_bars_and_beats():
    times = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
    grid = regular_beat_grid(times, beats_per_bar=4)
    assert numbers(grid) == [(1, 1), (1, 2), (1, 3), (1, 4), (2, 1), (2, 2)]
    assert [beat.time for beat in grid] == times


def test_regular_grid_with_pickup_beats():
    grid = regular_beat_grid([0.0, 0.5, 1.0, 1.5, 2.0], beats_per_bar=3, first_downbeat_index=2)
    assert numbers(grid) == [(0, 1), (0, 2), (1, 1), (1, 2), (1, 3)]


def test_grid_from_tracker_downbeats_uses_the_nearest_beat():
    grid = build_beat_grid([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0], downbeat_times=[0.52, 2.01])
    assert numbers(grid) == [(0, 1), (1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)]


def test_grid_from_tracker_needs_a_downbeat():
    with pytest.raises(ValueError, match="downbeat"):
        build_beat_grid([0.0, 0.5], downbeat_times=[])


@pytest.mark.parametrize("times", [[], [0.0, 0.5, 0.5], [1.0, 0.5]])
def test_beat_times_must_be_present_and_increasing(times):
    with pytest.raises(ValueError, match="[Bb]eat"):
        regular_beat_grid(times, beats_per_bar=4)


def test_beats_per_bar_must_be_positive():
    with pytest.raises(ValueError, match="beats_per_bar"):
        regular_beat_grid([0.0, 0.5], beats_per_bar=0)


@pytest.mark.parametrize("index", [-1, 2])
def test_first_downbeat_index_must_point_at_a_beat(index):
    with pytest.raises(ValueError, match="first_downbeat_index"):
        regular_beat_grid([0.0, 0.5], beats_per_bar=4, first_downbeat_index=index)


def test_boundaries_add_one_edge_after_the_last_beat():
    grid = regular_beat_grid([0.0, 0.5, 1.0], beats_per_bar=4)
    assert beat_boundaries(grid) == (0.0, 0.5, 1.0, 1.5)


def test_boundaries_of_a_single_beat_use_the_default_length():
    grid = regular_beat_grid([2.0], beats_per_bar=4)
    assert beat_boundaries(grid) == (2.0, 2.5)


def test_boundaries_need_a_beat():
    with pytest.raises(ValueError, match="At least one beat"):
        beat_boundaries([])
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_beats.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.grid.beats'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/grid/beats.py`:

```python
"""Build the beat grid: a time, a bar number and a beat number for each beat."""

from collections.abc import Sequence
from itertools import accumulate, pairwise

from jca_core.schema.records import Beat

DEFAULT_BEAT_SECONDS = 0.5


def regular_beat_grid(
    beat_times: Sequence[float], beats_per_bar: int, first_downbeat_index: int = 0
) -> tuple[Beat, ...]:
    """Number the beats from a time signature and the index of the first downbeat."""
    _check_times(beat_times)
    if beats_per_bar < 1:
        raise ValueError(f"beats_per_bar must be at least 1, got {beats_per_bar}")
    if not 0 <= first_downbeat_index < len(beat_times):
        raise ValueError(f"first_downbeat_index must point at a beat, got {first_downbeat_index}")
    flags = tuple(
        index >= first_downbeat_index and (index - first_downbeat_index) % beats_per_bar == 0
        for index in range(len(beat_times))
    )
    return _numbered(beat_times, flags)


def build_beat_grid(
    beat_times: Sequence[float], downbeat_times: Sequence[float]
) -> tuple[Beat, ...]:
    """Number the beats from tracker downbeats. Each downbeat marks its nearest beat."""
    _check_times(beat_times)
    if len(downbeat_times) == 0:
        raise ValueError("At least one downbeat is required")
    marked = frozenset(
        min(range(len(beat_times)), key=lambda index: abs(beat_times[index] - downbeat))
        for downbeat in downbeat_times
    )
    flags = tuple(index in marked for index in range(len(beat_times)))
    return _numbered(beat_times, flags)


def beat_boundaries(beats: Sequence[Beat]) -> tuple[float, ...]:
    """Return the beat times plus one closing edge, so that the last beat has a length."""
    times = tuple(beat.time for beat in beats)
    if not times:
        raise ValueError("At least one beat is required")
    last_length = times[-1] - times[-2] if len(times) > 1 else DEFAULT_BEAT_SECONDS
    return (*times, times[-1] + last_length)


def _check_times(beat_times: Sequence[float]) -> None:
    if len(beat_times) == 0:
        raise ValueError("At least one beat is required")
    if any(later <= earlier for earlier, later in pairwise(beat_times)):
        raise ValueError("Beat times must be strictly increasing")


def _next_position(position: tuple[int, int], is_downbeat: bool) -> tuple[int, int]:
    bar, beat = position
    return (bar + 1, 1) if is_downbeat else (bar, beat + 1)


def _numbered(beat_times: Sequence[float], downbeat_flags: Sequence[bool]) -> tuple[Beat, ...]:
    positions = tuple(accumulate(downbeat_flags, _next_position, initial=(0, 0)))[1:]
    return tuple(
        Beat(time=time, bar=bar, beat=beat)
        for time, (bar, beat) in zip(beat_times, positions, strict=True)
    )
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_beats.py -v`
Expected: PASS (13 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/grid/beats.py core/tests/test_beats.py
git commit -m "feat: build the beat grid with bar and beat numbers"
```

---

### Task 11: Snap chord changes to the grid

**Files:**
- Create: `core/src/jca_core/grid/snap.py`
- Test: `core/tests/test_snap.py`

This is decoder steps 1 and 2 of the design.

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_snap.py`:

```python
import pytest
from hypothesis import given
from hypothesis import strategies as st

from jca_core.grid.beats import beat_boundaries, regular_beat_grid
from jca_core.grid.snap import snap_segments, snap_time
from jca_core.schema.records import ChordSegment

BEAT_SECONDS = 0.5
# Two bars of 4/4 at 120 BPM: beats at 0.0 to 3.5, bar lines at 0.0 and 2.0, end at 4.0.
GRID = regular_beat_grid([index * BEAT_SECONDS for index in range(8)], beats_per_bar=4)


def seg(start: float, end: float, label: str) -> ChordSegment:
    return ChordSegment(start=start, end=end, label=label)


@pytest.mark.parametrize(
    ("time", "expected"),
    [
        (0.2, 0.0),
        (0.3, 0.5),
        (0.6, 0.5),
        (1.8, 2.0),
        (3.9, 4.0),
        (99.0, 4.0),
    ],
)
def test_snap_time_moves_to_the_nearest_beat(time, expected):
    assert snap_time(time, GRID) == expected


@pytest.mark.parametrize("time", [1.75, 2.25])
def test_a_change_half_a_beat_from_a_bar_line_moves_to_the_bar_line(time):
    assert snap_time(time, GRID) == 2.0


def test_a_tie_between_two_ordinary_beats_moves_to_the_earlier_beat():
    assert snap_time(0.75, GRID) == 0.5


def test_time_before_the_grid_moves_to_the_first_beat():
    late_grid = regular_beat_grid([1.0, 1.5, 2.0], beats_per_bar=4)
    assert snap_time(0.1, late_grid) == 1.0


def test_an_anticipated_change_lands_on_the_bar_line():
    segments = [seg(0.0, 1.8, "D:min7"), seg(1.8, 4.0, "G:7")]
    assert snap_segments(segments, GRID) == (seg(0.0, 2.0, "D:min7"), seg(2.0, 4.0, "G:7"))


def test_a_segment_shorter_than_a_beat_is_removed_and_its_neighbours_merge():
    segments = [seg(0.0, 1.9, "C:maj"), seg(1.9, 2.1, "F:maj"), seg(2.1, 4.0, "C:maj")]
    assert snap_segments(segments, GRID) == (seg(0.0, 4.0, "C:maj"),)


def test_segments_are_put_in_time_order():
    segments = [seg(2.0, 4.0, "G:7"), seg(0.0, 2.0, "D:min7")]
    assert snap_segments(segments, GRID) == (seg(0.0, 2.0, "D:min7"), seg(2.0, 4.0, "G:7"))


def test_snap_segments_does_not_change_its_input():
    segments = [seg(0.0, 1.8, "D:min7"), seg(1.8, 4.0, "G:7")]
    snap_segments(segments, GRID)
    assert segments == [seg(0.0, 1.8, "D:min7"), seg(1.8, 4.0, "G:7")]


@given(st.floats(min_value=0.0, max_value=4.0))
def test_a_change_inside_the_grid_never_moves_more_than_half_a_beat(time):
    snapped = snap_time(time, GRID)
    assert snapped in beat_boundaries(GRID)
    assert abs(snapped - time) <= BEAT_SECONDS / 2 + 1e-9
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_snap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.grid.snap'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/grid/snap.py`:

```python
"""Snap chord changes to the beat grid (decoder steps 1 and 2 of the design)."""

from bisect import bisect_left
from collections.abc import Sequence
from functools import reduce

from jca_core.grid.beats import beat_boundaries
from jca_core.schema.records import Beat, ChordSegment

TIE_TOLERANCE_SECONDS = 1e-6


def snap_time(time: float, beats: Sequence[Beat]) -> float:
    """Move a time to the nearest beat. A tie goes to a bar line, or else to the earlier beat."""
    return _snap(time, beat_boundaries(beats), _bar_lines(beats))


def snap_segments(
    segments: Sequence[ChordSegment], beats: Sequence[Beat]
) -> tuple[ChordSegment, ...]:
    """Snap both ends of each segment, drop segments with no length, merge equal neighbours."""
    edges = beat_boundaries(beats)
    bar_lines = _bar_lines(beats)
    ordered = sorted(segments, key=lambda segment: segment.start)
    snapped = (
        (_snap(segment.start, edges, bar_lines), _snap(segment.end, edges, bar_lines), segment)
        for segment in ordered
    )
    kept = (
        ChordSegment(start=start, end=end, label=segment.label)
        for start, end, segment in snapped
        if end > start
    )
    return reduce(_append_or_merge, kept, ())


def _bar_lines(beats: Sequence[Beat]) -> frozenset[float]:
    return frozenset(beat.time for beat in beats if beat.bar >= 1 and beat.beat == 1)


def _snap(time: float, edges: tuple[float, ...], bar_lines: frozenset[float]) -> float:
    index = bisect_left(edges, time)
    candidates = edges[max(0, index - 1) : index + 1]
    nearest = min(abs(time - edge) for edge in candidates)
    tied = tuple(
        edge for edge in candidates if abs(time - edge) - nearest <= TIE_TOLERANCE_SECONDS
    )
    on_bar_line = tuple(edge for edge in tied if edge in bar_lines)
    return (on_bar_line or tied)[0]


def _append_or_merge(
    merged: tuple[ChordSegment, ...], segment: ChordSegment
) -> tuple[ChordSegment, ...]:
    if merged and merged[-1].label == segment.label and merged[-1].end == segment.start:
        joined = ChordSegment(start=merged[-1].start, end=segment.end, label=segment.label)
        return (*merged[:-1], joined)
    return (*merged, segment)
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_snap.py -v`
Expected: PASS (15 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/grid/snap.py core/tests/test_snap.py
git commit -m "feat: snap chord changes to the beat grid"
```

---

### Task 12: One label for each beat

**Files:**
- Create: `core/src/jca_core/grid/resample.py`
- Test: `core/tests/test_resample.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_resample.py`:

```python
from hypothesis import given
from hypothesis import strategies as st

from jca_core.grid.beats import regular_beat_grid
from jca_core.grid.resample import labels_per_beat
from jca_core.schema.records import ChordSegment

GRID = regular_beat_grid([0.0, 0.5, 1.0, 1.5], beats_per_bar=4)
LABELS = ["C:maj", "D:min7", "G:7"]


def seg(start: float, end: float, label: str) -> ChordSegment:
    return ChordSegment(start=start, end=end, label=label)


def test_each_beat_takes_the_label_that_covers_it():
    segments = [seg(0.0, 1.0, "D:min7"), seg(1.0, 2.0, "G:7")]
    assert labels_per_beat(segments, GRID) == ("D:min7", "D:min7", "G:7", "G:7")


def test_a_beat_with_two_labels_takes_the_longer_one():
    segments = [seg(0.0, 0.2, "C:maj"), seg(0.2, 2.0, "G:7")]
    assert labels_per_beat(segments, GRID)[0] == "G:7"


def test_a_tie_takes_the_earlier_label():
    segments = [seg(0.0, 0.25, "C:maj"), seg(0.25, 2.0, "G:7")]
    assert labels_per_beat(segments, GRID)[0] == "C:maj"


def test_a_beat_with_no_segment_is_no_chord():
    segments = [seg(0.0, 1.0, "C:maj")]
    assert labels_per_beat(segments, GRID) == ("C:maj", "C:maj", "N", "N")


def test_no_segments_give_no_chord_on_every_beat():
    assert labels_per_beat([], GRID) == ("N", "N", "N", "N")


@given(
    st.lists(
        st.tuples(
            st.floats(min_value=0.0, max_value=3.0),
            st.floats(min_value=0.0, max_value=3.0),
            st.sampled_from(LABELS),
        ),
        max_size=12,
    )
)
def test_every_beat_gets_exactly_one_label(raw_segments):
    segments = [seg(start, start + length, label) for start, length, label in raw_segments]
    labels = labels_per_beat(segments, GRID)
    assert len(labels) == len(GRID)
    assert set(labels) <= {*LABELS, "N"}
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_resample.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.grid.resample'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/grid/resample.py`:

```python
"""Resample chord segments to the beat grid: one label for each beat."""

from collections.abc import Sequence
from itertools import pairwise

from jca_core.chords.harte import NO_CHORD
from jca_core.grid.beats import beat_boundaries
from jca_core.schema.records import Beat, ChordSegment


def labels_per_beat(segments: Sequence[ChordSegment], beats: Sequence[Beat]) -> tuple[str, ...]:
    """Return the label that covers most of each beat, or "N" where no segment does."""
    return tuple(
        _dominant_label(segments, start, end) for start, end in pairwise(beat_boundaries(beats))
    )


def _dominant_label(segments: Sequence[ChordSegment], start: float, end: float) -> str:
    overlaps = tuple(
        (min(segment.end, end) - max(segment.start, start), segment.label) for segment in segments
    )
    longest, label = max(overlaps, key=lambda overlap: overlap[0], default=(0.0, NO_CHORD))
    return label if longest > 0 else NO_CHORD
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_resample.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/grid/resample.py core/tests/test_resample.py
git commit -m "feat: resample chord segments to one label for each beat"
```

---

### Task 13: Bass root check

**Files:**
- Create: `core/src/jca_core/bass/root.py`
- Test: `core/tests/test_bass_root.py`

The test audio is made in code: a fundamental with a weaker octave and a weaker fifth above it, which is a rough stand-in for a plucked bass note.

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_bass_root.py`:

```python
import numpy as np
import pytest

from jca_core.bass.root import (
    bass_pitch_class_per_beat,
    pitch_class_energies,
    strongest_pitch_class,
)
from jca_core.grid.beats import regular_beat_grid

SAMPLE_RATE = 22050
BEAT_SECONDS = 0.5


def midi_to_hz(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12)


def bass_note(midi: int, seconds: float = BEAT_SECONDS) -> np.ndarray:
    time = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    frequency = midi_to_hz(midi)
    return (
        0.5 * np.sin(2 * np.pi * frequency * time)
        + 0.25 * np.sin(2 * np.pi * 2 * frequency * time)
        + 0.1 * np.sin(2 * np.pi * 3 * frequency * time)
    )


@pytest.mark.parametrize("midi", range(28, 52))  # E1, the lowest double bass string, to D#3
def test_strongest_pitch_class_of_a_bass_note(midi):
    assert strongest_pitch_class(bass_note(midi), SAMPLE_RATE) == midi % 12


def test_energies_have_one_value_for_each_pitch_class():
    energies = pitch_class_energies(bass_note(33), SAMPLE_RATE)  # A1
    assert energies.shape == (12,)
    assert int(np.argmax(energies)) == 9


def test_silence_has_no_pitch_class():
    assert strongest_pitch_class(np.zeros(SAMPLE_RATE), SAMPLE_RATE) is None


def test_empty_audio_has_no_pitch_class():
    assert strongest_pitch_class(np.zeros(0), SAMPLE_RATE) is None
    assert pitch_class_energies(np.zeros(0), SAMPLE_RATE).tolist() == [0.0] * 12


def test_audio_too_short_to_hold_a_bass_note_has_no_pitch_class():
    assert strongest_pitch_class(np.ones(4), SAMPLE_RATE) is None


def test_stereo_audio_is_mixed_to_mono():
    note = bass_note(38)  # D2
    stereo = np.column_stack([note, note])
    assert strongest_pitch_class(stereo, SAMPLE_RATE) == 2


def test_audio_with_three_dimensions_is_rejected():
    with pytest.raises(ValueError, match="1 or 2 dimensions"):
        strongest_pitch_class(np.zeros((4, 2, 2)), SAMPLE_RATE)


def test_one_pitch_class_for_each_beat():
    grid = regular_beat_grid([0.0, 0.5, 1.0, 1.5], beats_per_bar=4)
    silence = np.zeros(int(BEAT_SECONDS * SAMPLE_RATE))
    audio = np.concatenate([bass_note(38), bass_note(43), bass_note(36), silence])  # D, G, C
    assert bass_pitch_class_per_beat(audio, SAMPLE_RATE, grid) == (2, 7, 0, None)


def test_beats_after_the_end_of_the_audio_have_no_pitch_class():
    grid = regular_beat_grid([0.0, 0.5, 1.0, 1.5], beats_per_bar=4)
    assert bass_pitch_class_per_beat(bass_note(38), SAMPLE_RATE, grid) == (2, None, None, None)
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_bass_root.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.bass.root'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/bass/root.py`:

```python
"""Bass root check: the strongest pitch class of the bass stem on each beat."""

from collections.abc import Sequence
from itertools import pairwise

import numpy as np

from jca_core.grid.beats import beat_boundaries
from jca_core.pitch import PITCH_CLASS_COUNT
from jca_core.schema.records import Beat

MIN_BASS_HZ = 40.0  # just under E1, the lowest string of a double bass
MAX_BASS_HZ = 400.0
SILENCE_RMS = 1e-4
ZERO_PADDING_FACTOR = 4
A4_HZ = 440.0
A4_MIDI = 69


def to_mono(samples: np.ndarray) -> np.ndarray:
    """Return a new one-dimensional float array from mono or (frames, channels) audio."""
    if samples.ndim == 1:
        return samples.astype(np.float64)
    if samples.ndim == 2:
        return samples.mean(axis=1, dtype=np.float64)
    raise ValueError(f"Audio must have 1 or 2 dimensions, got {samples.ndim}")


def pitch_class_energies(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    """Return spectral energy in the bass range, summed into 12 pitch classes."""
    mono = to_mono(samples)
    if mono.size == 0:
        return np.zeros(PITCH_CLASS_COUNT)
    fft_size = ZERO_PADDING_FACTOR * int(2 ** np.ceil(np.log2(mono.size)))
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(mono.size), n=fft_size)) ** 2
    frequencies = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)
    in_range = (frequencies >= MIN_BASS_HZ) & (frequencies <= MAX_BASS_HZ)
    midi = A4_MIDI + PITCH_CLASS_COUNT * np.log2(frequencies[in_range] / A4_HZ)
    pitch_classes = np.round(midi).astype(int) % PITCH_CLASS_COUNT
    return np.bincount(pitch_classes, weights=spectrum[in_range], minlength=PITCH_CLASS_COUNT)


def strongest_pitch_class(samples: np.ndarray, sample_rate: int) -> int | None:
    """Return the pitch class with the most bass energy, or None for silence."""
    mono = to_mono(samples)
    if mono.size == 0 or float(np.sqrt(np.mean(mono**2))) < SILENCE_RMS:
        return None
    energies = pitch_class_energies(mono, sample_rate)
    if float(energies.sum()) <= 0.0:
        return None
    return int(np.argmax(energies))


def bass_pitch_class_per_beat(
    samples: np.ndarray, sample_rate: int, beats: Sequence[Beat]
) -> tuple[int | None, ...]:
    """Return the strongest bass pitch class for each beat of the grid."""
    mono = to_mono(samples)
    frame_edges = tuple(round(edge * sample_rate) for edge in beat_boundaries(beats))
    return tuple(
        strongest_pitch_class(mono[start:end], sample_rate) for start, end in pairwise(frame_edges)
    )
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_bass_root.py -v`
Expected: PASS (32 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/bass/root.py core/tests/test_bass_root.py
git commit -m "feat: find the strongest bass pitch class for each beat"
```

---

### Task 14: Decoder

**Files:**
- Create: `core/src/jca_core/decoder/draft.py`
- Test: `core/tests/test_draft.py`

This is decoder steps 3 to 5 of the design, on top of the snapping of Task 11.

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_draft.py`:

```python
import pytest

from jca_core.chords.agreement import Agreement
from jca_core.decoder.draft import decode
from jca_core.grid.beats import regular_beat_grid
from jca_core.schema.records import ChordSegment

# Two bars of 4/4 at 120 BPM.
GRID = regular_beat_grid([index * 0.5 for index in range(8)], beats_per_bar=4)
NO_BASS = (None,) * 8


def seg(start: float, end: float, label: str) -> ChordSegment:
    return ChordSegment(start=start, end=end, label=label)


def whole(label: str) -> list[ChordSegment]:
    return [seg(0.0, 4.0, label)]


def test_agreeing_models_give_the_chart_record_of_the_design():
    records = decode(GRID, whole("D:min7"), whole("D:min7"), (2,) * 8)
    assert len(records) == 8
    assert records[0].model_dump(mode="json") == {
        "bar": 1,
        "beat": 1,
        "time": 0.0,
        "lv_chordia": "D:min7",
        "btc": "D:min7",
        "bass_pitch_class": "D",
        "agreement": "A",
        "draft": {"root": "D", "class": "min", "extensions": ["b7"], "bass": "D"},
        "confidence": 0.8,
        "extensions_confidence": 0.6,
        "needs_review": False,
        "user_edit": None,
    }


def test_different_extensions_keep_the_primary_label_at_level_b():
    record = decode(GRID, whole("G:9"), whole("G:7"), NO_BASS)[0]
    assert record.agreement is Agreement.B
    assert record.draft.extensions == ("9",)
    assert record.confidence == 0.7
    assert record.extensions_confidence == 0.3
    assert record.needs_review is False


@pytest.mark.parametrize(
    ("btc_label", "level", "confidence"),
    [("C:7", Agreement.C, 0.4), ("F:maj7", Agreement.D, 0.2)],
)
def test_levels_c_and_d_are_marked_for_review(btc_label, level, confidence):
    record = decode(GRID, whole("C:maj7"), whole(btc_label), NO_BASS)[0]
    assert record.agreement is level
    assert record.confidence == confidence
    assert record.needs_review is True
    assert record.draft.root == "C"


def test_a_bass_note_that_fits_neither_model_marks_the_whole_bar():
    bass = (6, None, None, None, 0, None, None, None)  # F# on beat 1 of bar 1, C in bar 2
    records = decode(GRID, whole("C:maj"), whole("C:maj"), bass)
    assert [record.needs_review for record in records] == [True] * 4 + [False] * 4
    assert [record.confidence for record in records] == [0.6] * 4 + [0.8] * 4
    assert records[0].bass_pitch_class == "F#"


def test_a_bass_note_on_the_slash_bass_passes_the_check():
    bass = (4,) + (None,) * 7  # E under C/E
    records = decode(GRID, whole("C:maj/3"), whole("C:maj"), bass)
    assert records[0].needs_review is False


def test_a_bass_note_off_beat_one_is_not_checked():
    bass = (None, 6, 6, 6, None, 6, 6, 6)
    records = decode(GRID, whole("C:maj"), whole("C:maj"), bass)
    assert not any(record.needs_review for record in records)


def test_no_chordal_instrument_halves_the_confidence():
    record = decode(
        GRID, whole("C:maj"), whole("C:maj"), NO_BASS, has_chordal_instrument=False
    )[0]
    assert record.confidence == 0.4
    assert record.extensions_confidence == 0.3


def test_the_primary_model_can_be_btc():
    record = decode(GRID, whole("G:9"), whole("G:7"), NO_BASS, primary="btc")[0]
    assert record.draft.extensions == ()


def test_an_anticipated_change_starts_on_the_bar_line():
    segments = [seg(0.0, 1.8, "D:min7"), seg(1.8, 4.0, "G:7")]
    records = decode(GRID, segments, segments, NO_BASS)
    assert [record.lv_chordia for record in records] == ["D:min7"] * 4 + ["G:7"] * 4


def test_a_segment_shorter_than_a_beat_does_not_reach_the_chart():
    segments = [seg(0.0, 1.9, "C:maj"), seg(1.9, 2.1, "F:maj"), seg(2.1, 4.0, "C:maj")]
    records = decode(GRID, segments, segments, NO_BASS)
    assert {record.lv_chordia for record in records} == {"C:maj"}


def test_beats_that_a_model_does_not_cover_are_no_chord():
    records = decode(GRID, [seg(0.0, 2.0, "C:maj")], whole("C:maj"), NO_BASS)
    assert records[4].lv_chordia == "N"
    assert records[4].agreement is Agreement.D
    assert records[4].draft.root is None


def test_the_bass_list_must_match_the_grid():
    with pytest.raises(ValueError, match="one bass pitch class for each beat"):
        decode(GRID, whole("C:maj"), whole("C:maj"), (None,) * 3)
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_draft.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.decoder.draft'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/decoder/draft.py`:

```python
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
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_draft.py -v`
Expected: PASS (13 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/decoder/draft.py core/tests/test_draft.py
git commit -m "feat: decode two model outputs into a draft chart"
```

---

### Task 15: Separation plan

**Files:**
- Create: `core/src/jca_core/separation/plan.py`
- Test: `core/tests/test_plan.py`

The first six tests are the six rows of the "How the list is used" table in the design. The tests after them cover the cases that the table leaves open, including a computer with no 53-stem model.

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_plan.py`:

```python
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
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_plan.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.separation.plan'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/separation/plan.py`:

```python
"""Turn the user's instrument list into a separation plan."""

from collections.abc import Collection, Mapping, Sequence
from enum import StrEnum

from jca_core.schema.base import FrozenModel


class Instrument(StrEnum):
    PIANO = "piano"
    DOUBLE_BASS = "double bass"
    ELECTRIC_BASS = "electric bass"
    DRUMS = "drums"
    GUITAR = "guitar"
    VIBRAPHONE = "vibraphone"
    ALTO_SAX = "alto sax"
    TENOR_SAX = "tenor sax"
    BARITONE_SAX = "baritone sax"
    SOPRANO_SAX = "soprano sax"
    TRUMPET = "trumpet"
    TROMBONE = "trombone"
    CLARINET = "clarinet"
    FLUTE = "flute"
    VOCALS = "vocals"


class HornModel(StrEnum):
    NONE = "none"
    SAX = "sax"
    MULTI_STEM = "multi_stem"


SIX_STEM_OUTPUTS = ("vocals", "drums", "bass", "guitar", "piano", "other")
SIX_STEM_SOURCE: dict[Instrument, str] = {
    Instrument.VOCALS: "vocals",
    Instrument.DRUMS: "drums",
    Instrument.DOUBLE_BASS: "bass",
    Instrument.ELECTRIC_BASS: "bass",
    Instrument.GUITAR: "guitar",
    Instrument.PIANO: "piano",
}
SAXES = frozenset(
    {Instrument.ALTO_SAX, Instrument.TENOR_SAX, Instrument.BARITONE_SAX, Instrument.SOPRANO_SAX}
)
WINDS = SAXES | {Instrument.CLARINET, Instrument.FLUTE}
BRASS = frozenset({Instrument.TRUMPET, Instrument.TROMBONE})
CHORDAL = frozenset({Instrument.PIANO, Instrument.GUITAR})

SHARED_STEM_WARNING = (
    "{members}: the players share one stem named '{name}'. "
    "The split between similar horns is not reliable."
)
RESIDUE_WARNING = (
    "No separation model is available for {members}. The sound stays in the residue stem."
)
EXPERIMENTAL_WARNING = "{name} uses the text-prompted separator, which is experimental."


class Capabilities(FrozenModel):
    """The separation models that can run on this computer, besides the six-stem model."""

    sax_model: bool
    multi_stem: bool
    text_prompted: bool


ALL_MODELS = Capabilities(sax_model=True, multi_stem=True, text_prompted=True)


class StemRequest(FrozenModel):
    """One stem to keep: the name shown to the user and the model output it comes from."""

    name: str
    source: str


class SeparationPlan(FrozenModel):
    rhythm_stems: tuple[StemRequest, ...]
    horn_model: HornModel
    horn_stems: tuple[StemRequest, ...]
    experimental_stems: tuple[StemRequest, ...]
    warnings: tuple[str, ...]

    def folded_into_residue(self) -> tuple[str, ...]:
        """Six-stem outputs that are not kept. Their sound stays in the residue."""
        kept = {request.source for request in self.rhythm_stems}
        return tuple(output for output in SIX_STEM_OUTPUTS if output not in kept)


HornStage = tuple[HornModel, tuple[StemRequest, ...], tuple[str, ...]]


def has_chordal_instrument(instruments: Collection[Instrument]) -> bool:
    """True if the track has a piano or a guitar to play the chords."""
    return bool(CHORDAL & frozenset(instruments))


def normalise_other(other: Sequence[str]) -> tuple[str, ...]:
    """Trim and lower-case free-text instrument names, and remove blanks and repeats."""
    cleaned = (name.strip().lower() for name in other)
    return tuple(dict.fromkeys(name for name in cleaned if name))


def build_separation_plan(
    instruments: Collection[Instrument],
    capabilities: Capabilities,
    *,
    horn_counts: Mapping[Instrument, int] | None = None,
    other: Sequence[str] = (),
) -> SeparationPlan:
    """Return the stems to keep, the horn model to run and the warnings for the user."""
    selected = frozenset(instruments)
    counts = _checked_counts(horn_counts)
    horn_model, horn_stems, horn_warnings = _horn_stage(
        selected & (WINDS | BRASS), counts, capabilities
    )
    experimental_stems, experimental_warnings = _experimental_stage(selected, other, capabilities)
    return SeparationPlan(
        rhythm_stems=_rhythm_stems(selected),
        horn_model=horn_model,
        horn_stems=horn_stems,
        experimental_stems=experimental_stems,
        warnings=(*horn_warnings, *experimental_warnings),
    )


def _checked_counts(horn_counts: Mapping[Instrument, int] | None) -> dict[Instrument, int]:
    counts = dict(horn_counts or {})
    invalid = sorted(instrument.value for instrument, count in counts.items() if count < 1)
    if invalid:
        raise ValueError(f"Horn counts must be at least 1: {', '.join(invalid)}")
    return counts


def _rhythm_stems(selected: frozenset[Instrument]) -> tuple[StemRequest, ...]:
    members_by_output = (
        (output, sorted(i for i in selected if SIX_STEM_SOURCE.get(i) == output))
        for output in SIX_STEM_OUTPUTS
    )
    return tuple(
        StemRequest(name=members[0].value if len(members) == 1 else output, source=output)
        for output, members in members_by_output
        if members
    )


def _listed(members: Collection[Instrument]) -> str:
    return " and ".join(sorted(member.value for member in members))


def _is_one_player(members: frozenset[Instrument], counts: Mapping[Instrument, int]) -> bool:
    return len(members) == 1 and counts.get(next(iter(members)), 1) == 1


def _group(
    members: frozenset[Instrument], counts: Mapping[Instrument, int], source: str, family: str
) -> tuple[StemRequest, tuple[str, ...]]:
    """Return one stem for a group of horns, with a warning if players share it."""
    if _is_one_player(members, counts):
        return StemRequest(name=next(iter(members)).value, source=source), ()
    if len(members) == 1:
        name = f"{next(iter(members)).value} section"
    else:
        name = "saxes" if members <= SAXES else family
    warning = SHARED_STEM_WARNING.format(members=_listed(members), name=name)
    return StemRequest(name=name, source=source), (warning,)


def _horn_stage(
    horns: frozenset[Instrument], counts: Mapping[Instrument, int], capabilities: Capabilities
) -> HornStage:
    if not horns:
        return HornModel.NONE, (), ()
    if horns <= SAXES and capabilities.sax_model:
        request, warnings = _group(horns, counts, "sax", "saxes")
        return HornModel.SAX, (request,), warnings
    if capabilities.multi_stem:
        families = ((horns & WINDS, "wind", "winds"), (horns & BRASS, "brass", "brass"))
        groups = tuple(
            _group(members, counts, source, family)
            for members, source, family in families
            if members
        )
        requests = tuple(request for request, _ in groups)
        warnings = tuple(warning for _, group_warnings in groups for warning in group_warnings)
        return HornModel.MULTI_STEM, requests, warnings
    saxes = horns & SAXES
    if saxes and capabilities.sax_model:
        request, warnings = _group(saxes, counts, "sax", "saxes")
        left_out = RESIDUE_WARNING.format(members=_listed(horns - saxes))
        return HornModel.SAX, (request,), (*warnings, left_out)
    return HornModel.NONE, (), (RESIDUE_WARNING.format(members=_listed(horns)),)


def _experimental_stage(
    selected: frozenset[Instrument], other: Sequence[str], capabilities: Capabilities
) -> tuple[tuple[StemRequest, ...], tuple[str, ...]]:
    vibraphone = (Instrument.VIBRAPHONE.value,) if Instrument.VIBRAPHONE in selected else ()
    names = (*vibraphone, *normalise_other(other))
    if not names:
        return (), ()
    if not capabilities.text_prompted:
        return (), (RESIDUE_WARNING.format(members=" and ".join(names)),)
    requests = tuple(StemRequest(name=name, source=name) for name in names)
    warnings = tuple(EXPERIMENTAL_WARNING.format(name=name) for name in names)
    return requests, warnings
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_plan.py -v`
Expected: PASS (21 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/separation/plan.py core/tests/test_plan.py
git commit -m "feat: build the separation plan from the instrument list"
```

---

### Task 16: Residue stem

**Files:**
- Create: `core/src/jca_core/separation/residue.py`
- Test: `core/tests/test_residue.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_residue.py`:

```python
import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from jca_core.separation.residue import compute_residue

FRAMES = 64
CHANNELS = 2


def test_residue_is_the_mix_minus_all_stems():
    mix = np.array([[1.0, 1.0], [0.5, -0.5]])
    piano = np.array([[0.25, 0.5], [0.5, 0.0]])
    bass = np.array([[0.25, 0.25], [0.0, -0.25]])
    expected = np.array([[0.5, 0.25], [0.0, -0.25]])
    np.testing.assert_allclose(compute_residue(mix, [piano, bass]), expected)


def test_with_no_stems_the_residue_is_the_mix():
    mix = np.array([[0.1, -0.2], [0.3, 0.4]])
    np.testing.assert_allclose(compute_residue(mix, []), mix)


def test_residue_keeps_the_shape_of_the_mix():
    mix = np.zeros((FRAMES, CHANNELS))
    assert compute_residue(mix, [np.zeros((FRAMES, CHANNELS))]).shape == (FRAMES, CHANNELS)


def test_a_stem_with_another_length_is_rejected():
    mix = np.zeros((FRAMES, CHANNELS))
    with pytest.raises(ValueError, match="Stem 1 has shape"):
        compute_residue(mix, [np.zeros((FRAMES, CHANNELS)), np.zeros((FRAMES - 1, CHANNELS))])


def test_inputs_are_not_changed():
    mix = np.ones((FRAMES, CHANNELS))
    stem = np.full((FRAMES, CHANNELS), 0.25)
    compute_residue(mix, [stem])
    np.testing.assert_array_equal(mix, np.ones((FRAMES, CHANNELS)))
    np.testing.assert_array_equal(stem, np.full((FRAMES, CHANNELS), 0.25))


@given(st.integers(min_value=0, max_value=2**32 - 1), st.integers(min_value=1, max_value=6))
def test_stems_plus_residue_equal_the_mix(seed, stem_count):
    random = np.random.default_rng(seed)
    mix = random.uniform(-1.0, 1.0, size=(FRAMES, CHANNELS))
    stems = [random.uniform(-1.0, 1.0, size=(FRAMES, CHANNELS)) for _ in range(stem_count)]
    residue = compute_residue(mix, stems)
    np.testing.assert_allclose(residue + sum(stems), mix, atol=1e-12)
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_residue.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.separation.residue'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/separation/residue.py`:

```python
"""The residue stem: the mix minus every kept stem."""

from collections.abc import Sequence
from functools import reduce

import numpy as np


def compute_residue(mix: np.ndarray, stems: Sequence[np.ndarray]) -> np.ndarray:
    """Return a new array, mix minus all stems. Every stem must have the shape of the mix."""
    for index, stem in enumerate(stems):
        if stem.shape != mix.shape:
            raise ValueError(
                f"Stem {index} has shape {stem.shape}, but the mix has shape {mix.shape}"
            )
    return reduce(np.subtract, stems, mix.astype(np.float64))
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_residue.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/separation/residue.py core/tests/test_residue.py
git commit -m "feat: compute the residue stem"
```

---

### Task 17: Cache key

**Files:**
- Create: `core/src/jca_core/cache/key.py`
- Test: `core/tests/test_cache_key.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_cache_key.py`:

```python
import hashlib
import re

import pytest

from jca_core.cache.key import file_sha256, stem_cache_key
from jca_core.separation.plan import Instrument

AUDIO = "a" * 64
SEPARATOR = "bs-roformer-sw"
TRIO = [Instrument.PIANO, Instrument.DOUBLE_BASS, Instrument.DRUMS]


def test_key_is_a_stable_sha256():
    key = stem_cache_key(AUDIO, SEPARATOR, TRIO)
    assert re.fullmatch(r"[0-9a-f]{64}", key)
    assert key == stem_cache_key(AUDIO, SEPARATOR, TRIO)


def test_key_does_not_depend_on_the_order_of_the_instruments():
    assert stem_cache_key(AUDIO, SEPARATOR, TRIO) == stem_cache_key(AUDIO, SEPARATOR, TRIO[::-1])


def test_key_changes_with_each_input():
    base = stem_cache_key(AUDIO, SEPARATOR, TRIO)
    changed = {
        stem_cache_key("b" * 64, SEPARATOR, TRIO),
        stem_cache_key(AUDIO, "htdemucs_6s", TRIO),
        stem_cache_key(AUDIO, SEPARATOR, [*TRIO, Instrument.ALTO_SAX]),
        stem_cache_key(AUDIO, SEPARATOR, TRIO, other=["organ"]),
        stem_cache_key(
            AUDIO, SEPARATOR, [*TRIO, Instrument.TRUMPET], horn_counts={Instrument.TRUMPET: 2}
        ),
    }
    assert base not in changed
    assert len(changed) == 5


def test_free_text_instruments_are_normalised():
    first = stem_cache_key(AUDIO, SEPARATOR, TRIO, other=["  Organ "])
    second = stem_cache_key(AUDIO, SEPARATOR, TRIO, other=["organ", "ORGAN"])
    assert first == second


def test_a_count_of_one_is_the_same_as_no_count():
    with_trumpet = [*TRIO, Instrument.TRUMPET]
    first = stem_cache_key(AUDIO, SEPARATOR, with_trumpet, horn_counts={Instrument.TRUMPET: 1})
    assert first == stem_cache_key(AUDIO, SEPARATOR, with_trumpet)


@pytest.mark.parametrize("audio", ["", "abc", "A" * 64, "g" * 64])
def test_audio_hash_must_be_a_sha256(audio):
    with pytest.raises(ValueError, match="64 lowercase hex"):
        stem_cache_key(audio, SEPARATOR, TRIO)


def test_separator_must_be_named():
    with pytest.raises(ValueError, match="separator"):
        stem_cache_key(AUDIO, "", TRIO)


def test_file_sha256_hashes_the_file_content(tmp_path):
    path = tmp_path / "take.flac"
    path.write_bytes(b"not really audio")
    assert file_sha256(path) == hashlib.sha256(b"not really audio").hexdigest()


def test_file_sha256_of_a_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        file_sha256(tmp_path / "missing.flac")
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_cache_key.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.cache.key'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/cache/key.py`:

```python
"""Cache keys: stems are cached by the audio hash plus the instrument list."""

import hashlib
import json
import re
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path

from jca_core.separation.plan import Instrument, normalise_other

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def file_sha256(path: Path) -> str:
    """Return the SHA-256 of a file, read in chunks."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def stem_cache_key(
    audio_sha256: str,
    separator: str,
    instruments: Collection[Instrument],
    *,
    horn_counts: Mapping[Instrument, int] | None = None,
    other: Sequence[str] = (),
) -> str:
    """Return one key for the audio, the separator and the instrument list, in any order."""
    if not _SHA256_PATTERN.fullmatch(audio_sha256):
        raise ValueError("audio_sha256 must be 64 lowercase hex characters")
    if not separator:
        raise ValueError("separator must not be empty")
    payload = {
        "audio": audio_sha256,
        "separator": separator,
        "instruments": sorted({instrument.value for instrument in instruments}),
        "horn_counts": sorted(
            [instrument.value, count]
            for instrument, count in (horn_counts or {}).items()
            if count != 1
        ),
        "other": sorted(normalise_other(other)),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_cache_key.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/cache/key.py core/tests/test_cache_key.py
git commit -m "feat: add the file hash and the stem cache key"
```

---

### Task 18: Text chart export

**Files:**
- Create: `core/src/jca_core/export/text_chart.py`
- Test: `core/tests/test_text_chart.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_text_chart.py`:

```python
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
    assert text_chart(records) == (
        "| Dm7   | G7    | Cmaj7 | Cmaj7 |\n"
        "| Fmaj7 | Bm7b5 | E7    | Am7   |\n"
    )


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
    assert text_chart(records) == (
        "| G7 | C  | C  | C  | C  |\n"
        "| C  |\n"
    )


def test_no_chord_is_written_as_nc():
    assert text_chart(bar(1, "N")) == "| N.C. |\n"


def test_an_empty_chart_is_an_empty_string():
    assert text_chart([]) == ""
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_text_chart.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.export.text_chart'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/export/text_chart.py`:

```python
"""Export the chart as text, with four bars on each line."""

from collections.abc import Sequence
from itertools import batched, groupby, pairwise

from jca_core.chords.display import chord_symbol
from jca_core.schema.records import ChartRecord

BARS_PER_LINE = 4
HELD_BEAT = "/"


def text_chart(records: Sequence[ChartRecord]) -> str:
    """Return the chart as lines of bars. A user edit replaces the draft label."""
    cells = tuple(
        (number, _bar_cell(tuple(_symbol(record) for record in group)))
        for number, group in groupby(records, key=lambda record: record.bar)
    )
    if not cells:
        return ""
    width = max(len(cell) for _, cell in cells)
    pickup = tuple(cell for number, cell in cells if number < 1)
    main = tuple(cell for number, cell in cells if number >= 1)
    rows = tuple(batched(main, BARS_PER_LINE)) or ((),)
    lines = ((*pickup, *rows[0]), *rows[1:])
    return "".join(_line(row, width) for row in lines)


def _symbol(record: ChartRecord) -> str:
    return chord_symbol(record.user_edit or record.draft)


def _bar_cell(symbols: tuple[str, ...]) -> str:
    """One chord for a whole bar, two for two equal halves, held-beat marks otherwise."""
    if len(set(symbols)) == 1:
        return symbols[0]
    half = len(symbols) // 2
    is_even = len(symbols) % 2 == 0
    if is_even and len(set(symbols[:half])) == 1 and len(set(symbols[half:])) == 1:
        return f"{symbols[0]} {symbols[half]}"
    changes = (
        HELD_BEAT if current == previous else current for previous, current in pairwise(symbols)
    )
    return " ".join((symbols[0], *changes))


def _line(cells: Sequence[str], width: int) -> str:
    return "| " + " | ".join(cell.ljust(width) for cell in cells) + " |\n"
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_text_chart.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/export/text_chart.py core/tests/test_text_chart.py
git commit -m "feat: export the chart as text with four bars on each line"
```

---

### Task 19: JSON export

**Files:**
- Create: `core/src/jca_core/export/json_export.py`
- Test: `core/tests/test_json_export.py`

- [ ] **Step 1: Write the failing test**

Create `core/tests/test_json_export.py`:

```python
import json

import pytest

from jca_core.chords.harte import parse_chord
from jca_core.chords.parts import chord_parts
from jca_core.decoder.draft import decode
from jca_core.export.json_export import analysis_from_json, analysis_to_json
from jca_core.grid.beats import regular_beat_grid
from jca_core.schema.records import AnalysisDocument, ChordSegment

GRID = regular_beat_grid([0.0, 0.5, 1.0, 1.5], beats_per_bar=4)
LV = (ChordSegment(start=0.0, end=2.0, label="D:min7"),)
BTC = (ChordSegment(start=0.0, end=2.0, label="D:min"),)


def document() -> AnalysisDocument:
    chart = decode(GRID, LV, BTC, (2, None, None, None))
    return AnalysisDocument(beats=GRID, lv_chordia=LV, btc=BTC, chart=chart)


def test_json_round_trip_gives_the_same_document():
    original = document()
    assert analysis_from_json(analysis_to_json(original)) == original


def test_json_holds_times_beats_both_models_and_the_edits():
    data = json.loads(analysis_to_json(document()))
    assert data["schema_version"] == 1
    assert data["beats"][0] == {"time": 0.0, "bar": 1, "beat": 1}
    assert data["lv_chordia"] == [{"start": 0.0, "end": 2.0, "label": "D:min7"}]
    assert data["btc"] == [{"start": 0.0, "end": 2.0, "label": "D:min"}]
    assert data["chart"][0]["draft"]["class"] == "min"
    assert data["chart"][0]["user_edit"] is None


def test_a_user_edit_survives_the_round_trip():
    original = document()
    edit = chord_parts(parse_chord("D:min9"))
    edited_chart = (original.chart[0].model_copy(update={"user_edit": edit}), *original.chart[1:])
    edited = original.model_copy(update={"chart": edited_chart})
    restored = analysis_from_json(analysis_to_json(edited))
    assert restored.chart[0].user_edit == edit
    assert restored.chart[0].draft == original.chart[0].draft


@pytest.mark.parametrize("text", ["", "not json", "{}", '{"beats": []}'])
def test_invalid_json_raises_a_clear_error(text):
    with pytest.raises(ValueError, match="Invalid analysis JSON"):
        analysis_from_json(text)
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run --directory core pytest tests/test_json_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jca_core.export.json_export'`

- [ ] **Step 3: Write the implementation**

Create `core/src/jca_core/export/json_export.py`:

```python
"""Export the whole analysis as JSON, and read it back."""

from pydantic import ValidationError

from jca_core.schema.records import AnalysisDocument

JSON_INDENT = 2


def analysis_to_json(document: AnalysisDocument) -> str:
    """Return the document as JSON: times, beats, both model outputs and the user edits."""
    return document.model_dump_json(indent=JSON_INDENT)


def analysis_from_json(text: str) -> AnalysisDocument:
    """Parse and validate an exported document. Raises ValueError for bad input."""
    try:
        return AnalysisDocument.model_validate_json(text)
    except ValidationError as error:
        raise ValueError(f"Invalid analysis JSON: {error.error_count()} problem(s)") from error
```

- [ ] **Step 4: Run the test to see it pass**

Run: `uv run --directory core pytest tests/test_json_export.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add core/src/jca_core/export/json_export.py core/tests/test_json_export.py
git commit -m "feat: export the analysis as JSON"
```

---

### Task 20: End-to-end check, coverage gate and lint

**Files:**
- Test: `core/tests/test_end_to_end.py`

This test joins the modules the way Phase 1b will: a beat grid, two model outputs, a bass stem, then the decoder and both exports. It needs no new code, so it should pass when first run. If it fails, the fault is in the join between two modules.

- [ ] **Step 1: Write the test**

Create `core/tests/test_end_to_end.py`:

```python
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
```

- [ ] **Step 2: Run the test**

Run: `uv run --directory core pytest tests/test_end_to_end.py -v`
Expected: PASS (1 passed)

- [ ] **Step 3: Run the whole suite with the coverage gate**

Run: `uv run --directory core pytest --cov --cov-report=term-missing`
Expected: 323 passed, total coverage 100.00%, and no "FAIL Required test coverage of 80% not reached" line.

- [ ] **Step 4: Run the linter**

Run: `uv run --directory core ruff check .`
Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add core/tests/test_end_to_end.py
git commit -m "test: join the core modules end to end"
```

---

## Exit gate for Phase 1a

- [ ] Every row of the agreement table in the design passes as a test (Task 7).
- [ ] Every row of the "How the list is used" table in the design passes as a test (Task 15).
- [ ] The chart record of the design validates and comes out of the decoder (Tasks 9 and 14).
- [ ] The whole suite passes with coverage above 80% (Task 20).
- [ ] The twelve decisions at the top of this plan are confirmed or changed by the user.

## What Phase 1b takes from this package

| Phase 1b needs | It calls |
| --- | --- |
| Which models to run for an instrument list | `build_separation_plan`, `has_chordal_instrument` |
| Where the stems are cached | `file_sha256`, `stem_cache_key` |
| The residue stem | `compute_residue` |
| The bar grid from the beat tracker | `build_beat_grid`, `regular_beat_grid` |
| The bass root check | `bass_pitch_class_per_beat` |
| The comparison JSON | `decode`, `AnalysisDocument`, `analysis_to_json` |
| The text chart | `text_chart` |
