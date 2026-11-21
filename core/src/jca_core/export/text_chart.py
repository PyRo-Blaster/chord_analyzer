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
