import type { BeatView, ChartEdit, ChordParts, ChordView, PartsView } from "../api/types";
import type { LoopRange } from "../audio/engine";

export const BARS_PER_ROW = 4;
const MIN_TAPS = 4;
const MIN_TEMPO_BPM = 20;
const MAX_TEMPO_BPM = 400;

export interface Bar {
  readonly number: number;
  readonly beats: readonly BeatView[];
}

export interface Segment {
  readonly key: string;
  readonly beats: readonly BeatView[];
}

export interface Selection {
  readonly anchor: number;
  readonly focus: number;
}

export interface TappedTempo {
  readonly tempo_bpm: number;
  readonly first_beat_time: number;
}

export function barsOf(beats: readonly BeatView[]): readonly Bar[] {
  return beats.reduce<readonly Bar[]>((bars, beat) => {
    const last = bars.at(-1);
    if (last !== undefined && last.number === beat.bar) {
      return [...bars.slice(0, -1), { number: last.number, beats: [...last.beats, beat] }];
    }
    return [...bars, { number: beat.bar, beats: [beat] }];
  }, []);
}

/** Four bars on each line; bars before bar 1 (a pickup) lead the first line. */
export function rowsOf(bars: readonly Bar[]): readonly (readonly Bar[])[] {
  const pickup = bars.filter((bar) => bar.number < 1);
  const main = bars.filter((bar) => bar.number >= 1);
  const rows: Bar[][] = [];
  for (let start = 0; start < main.length; start += BARS_PER_ROW) {
    rows.push(main.slice(start, start + BARS_PER_ROW));
  }
  const [first = [], ...rest] = rows;
  return pickup.length === 0 && rows.length === 0 ? [] : [[...pickup, ...first], ...rest];
}

export function segmentsOf(beats: readonly BeatView[], keyOf: (beat: BeatView) => string): readonly Segment[] {
  return beats.reduce<readonly Segment[]>((segments, beat) => {
    const key = keyOf(beat);
    const last = segments.at(-1);
    if (last !== undefined && last.key === key) {
      return [...segments.slice(0, -1), { key, beats: [...last.beats, beat] }];
    }
    return [...segments, { key, beats: [beat] }];
  }, []);
}

/** What the chart shows for a beat: the user's edit if there is one, otherwise the draft. */
export function shown(beat: BeatView): PartsView {
  return beat.user_edit ?? beat.draft;
}

export function select(current: Selection | null, index: number, extend: boolean): Selection {
  return extend && current !== null ? { anchor: current.anchor, focus: index } : { anchor: index, focus: index };
}

/** Select beats `from`..`to` (a whole chord); with `extend`, stretch the selection to cover them. */
export function selectRange(current: Selection | null, from: number, to: number, extend: boolean): Selection {
  if (!extend || current === null) {
    return { anchor: from, focus: to };
  }
  const low = Math.min(current.anchor, current.focus);
  const high = Math.max(current.anchor, current.focus);
  return to > high ? { anchor: low, focus: to } : { anchor: high, focus: Math.min(from, low) };
}

export function selectedIndices(selection: Selection | null): readonly number[] {
  if (selection === null) {
    return [];
  }
  const from = Math.min(selection.anchor, selection.focus);
  const to = Math.max(selection.anchor, selection.focus);
  return Array.from({ length: to - from + 1 }, (_, offset) => from + offset);
}

export function editsFor(view: ChordView, selection: Selection | null, parts: ChordParts | null): readonly ChartEdit[] {
  return selectedIndices(selection)
    .map((index) => view.beats[index])
    .filter((beat): beat is BeatView => beat !== undefined)
    .map((beat) => ({ time: beat.time, user_edit: parts }));
}

export function loopRangeOf(view: ChordView, selection: Selection | null): LoopRange | null {
  const indices = selectedIndices(selection);
  const first = view.beats[indices[0] ?? -1];
  const lastIndex = indices.at(-1);
  if (first === undefined || lastIndex === undefined) {
    return null;
  }
  const end = view.beats[lastIndex + 1]?.time ?? view.duration;
  return { start: first.time, end };
}

/** Index of the beat playing at `time` (the last beat that starts at or before it), or -1. */
export function beatIndexAt(beats: readonly BeatView[], time: number): number {
  let low = 0;
  let high = beats.length - 1;
  let found = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if ((beats[middle]?.time ?? Infinity) <= time) {
      found = middle;
      low = middle + 1;
    } else {
      high = middle - 1;
    }
  }
  return found;
}

/** Tempo from the median gap between taps; the phase from the first tap. Track times in seconds. */
export function tapTempo(taps: readonly number[]): TappedTempo | null {
  if (taps.length < MIN_TAPS) {
    return null;
  }
  const gaps = taps.slice(1).map((time, index) => time - (taps[index] ?? time));
  const sorted = [...gaps].sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)] ?? 0;
  if (median <= 0) {
    return null;
  }
  const tempo = Math.round((60 / median) * 10) / 10;
  if (tempo < MIN_TEMPO_BPM || tempo > MAX_TEMPO_BPM) {
    return null;
  }
  const period = 60 / tempo;
  const first = taps[0] ?? 0;
  const phase = first - Math.floor(first / period) * period;
  return { tempo_bpm: tempo, first_beat_time: Math.round(phase * 1000) / 1000 };
}
