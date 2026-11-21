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
