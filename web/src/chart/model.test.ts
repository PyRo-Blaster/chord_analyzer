import { describe, expect, it } from "vitest";
import type { BeatView, ChordParts, ChordView } from "../api/types";
import {
  barsOf,
  beatIndexAt,
  editsFor,
  loopRangeOf,
  rowsOf,
  segmentsOf,
  select,
  selectedIndices,
  shown,
  tapTempo,
} from "./model";

function parts(root: string | null, klass: ChordParts["class"] = "maj"): ChordParts {
  return { root, class: root === null ? null : klass, extensions: [], bass: root };
}

function beat(index: number, bar: number, beatInBar: number, symbol = "C", edit: string | null = null): BeatView {
  const tiers = (text: string) => ({ symbol: text, tier1: text, tier2: "" });
  return {
    index,
    bar,
    beat: beatInBar,
    time: index * 0.5,
    agreement: "A",
    needs_review: false,
    confidence: 0.8,
    extensions_confidence: 0.6,
    bass_pitch_class: "C",
    lv_chordia: { label: "C:maj", parts: parts("C"), ...tiers("C") },
    btc: { label: "C:maj", parts: parts("C"), ...tiers("C") },
    draft: { parts: parts("C"), ...tiers(symbol) },
    user_edit: edit === null ? null : { parts: parts("D", "min"), ...tiers(edit) },
  };
}

const BEATS = [0, 1, 2, 3, 4, 5, 6, 7, 8].map((index) => beat(index, index === 0 ? 0 : Math.floor((index - 1) / 4) + 1, index === 0 ? 1 : ((index - 1) % 4) + 1));
const VIEW: ChordView = {
  beats: BEATS,
  duration: 4.5,
  unplaced_edits: 0,
  grid: { beats_per_bar: null, first_downbeat_index: null, tempo_bpm: null, first_beat_time: null },
};

describe("bars and rows", () => {
  it("groups beats into bars, with the pickup bar first", () => {
    const bars = barsOf(BEATS);
    expect(bars.map((bar) => [bar.number, bar.beats.length])).toEqual([
      [0, 1],
      [1, 4],
      [2, 4],
    ]);
  });

  it("puts four bars on each line, the pickup leading the first line", () => {
    const many = Array.from({ length: 21 }, (_, index) => beat(index, Math.floor(index / 4), (index % 4) + 1));
    expect(rowsOf(barsOf(many)).map((row) => row.map((bar) => bar.number))).toEqual([
      [0, 1, 2, 3, 4],
      [5],
    ]);
  });
});

describe("segments", () => {
  it("joins beats that show the same label", () => {
    const bar = [beat(0, 1, 1, "Dm7"), beat(1, 1, 2, "Dm7"), beat(2, 1, 3, "G7"), beat(3, 1, 4, "G7", "G13")];
    expect(segmentsOf(bar, (item) => shown(item).symbol).map((segment) => [segment.key, segment.beats.length])).toEqual([
      ["Dm7", 2],
      ["G7", 1],
      ["G13", 1],
    ]);
  });

  it("shows the user edit before the draft", () => {
    expect(shown(beat(0, 1, 1, "C", "Dm")).symbol).toBe("Dm");
    expect(shown(beat(0, 1, 1, "C")).symbol).toBe("C");
  });
});

describe("selection", () => {
  it("selects one beat, then extends to another in either direction", () => {
    const one = select(null, 3, false);
    expect(selectedIndices(one)).toEqual([3]);
    expect(selectedIndices(select(one, 6, true))).toEqual([3, 4, 5, 6]);
    expect(selectedIndices(select(one, 1, true))).toEqual([1, 2, 3]);
    expect(selectedIndices(select(one, 5, false))).toEqual([5]);
    expect(selectedIndices(null)).toEqual([]);
  });

  it("makes one edit for each selected beat", () => {
    const edits = editsFor(VIEW, select(select(null, 2, false), 3, true), parts("D", "min"));
    expect(edits).toEqual([
      { time: 1.0, user_edit: parts("D", "min") },
      { time: 1.5, user_edit: parts("D", "min") },
    ]);
  });

  it("loops from the first selected beat to the end of the last", () => {
    expect(loopRangeOf(VIEW, select(select(null, 1, false), 4, true))).toEqual({ start: 0.5, end: 2.5 });
    expect(loopRangeOf(VIEW, select(null, 8, false))).toEqual({ start: 4.0, end: 4.5 });
    expect(loopRangeOf(VIEW, null)).toBeNull();
  });
});

describe("beatIndexAt", () => {
  it.each([
    [-1, -1],
    [0, 0],
    [0.74, 1],
    [1.0, 2],
    [99, 8],
  ])("time %s is beat %s", (time, index) => {
    expect(beatIndexAt(BEATS, time)).toBe(index);
  });
});

describe("tapTempo", () => {
  it("needs four taps", () => {
    expect(tapTempo([1, 1.5, 2])).toBeNull();
  });

  it("takes the median gap as the tempo and the first tap as the phase", () => {
    expect(tapTempo([10.3, 10.9, 11.5, 12.1, 13.4])).toEqual({ tempo_bpm: 100, first_beat_time: 0.1 });
  });

  it("refuses a tempo outside 20 to 400 BPM", () => {
    expect(tapTempo([0, 0.1, 0.2, 0.3])).toBeNull();
    expect(tapTempo([0, 4, 8, 12])).toBeNull();
  });
});
