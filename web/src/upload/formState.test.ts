import { describe, expect, it } from "vitest";
import type { Catalogue } from "../api/types";
import {
  EMPTY_FORM,
  applyPreset,
  formError,
  isAcceptedFile,
  setHornCount,
  toOptions,
  toggleInstrument,
} from "./formState";

const CATALOGUE: Catalogue = {
  instruments: ["piano", "double bass", "drums", "tenor sax", "trumpet"],
  horns: ["tenor sax", "trumpet"],
  presets: [
    { id: "piano-trio", label: "Piano trio", instruments: ["piano", "double bass", "drums"], horn_counts: {} },
    { id: "brass", label: "Brass", instruments: ["trumpet"], horn_counts: { trumpet: 4 } },
  ],
};

describe("form state", () => {
  it("applies a preset", () => {
    const state = applyPreset(EMPTY_FORM, CATALOGUE, "brass");
    expect(state.selected).toEqual(["trumpet"]);
    expect(state.hornCounts).toEqual({ trumpet: 4 });
    expect(state.presetId).toBe("brass");
  });

  it("ignores an unknown preset", () => {
    expect(applyPreset(EMPTY_FORM, CATALOGUE, "nope")).toBe(EMPTY_FORM);
  });

  it("toggles an instrument without changing the old state and clears the preset", () => {
    const trio = applyPreset(EMPTY_FORM, CATALOGUE, "piano-trio");
    const withoutDrums = toggleInstrument(trio, "drums");
    expect(withoutDrums.selected).toEqual(["piano", "double bass"]);
    expect(withoutDrums.presetId).toBeNull();
    expect(trio.selected).toEqual(["piano", "double bass", "drums"]);
    expect(toggleInstrument(withoutDrums, "drums").selected).toEqual(["piano", "double bass", "drums"]);
  });

  it("removing a horn removes its count", () => {
    const brass = applyPreset(EMPTY_FORM, CATALOGUE, "brass");
    expect(toggleInstrument(brass, "trumpet").hornCounts).toEqual({});
  });

  it("keeps counts between 1 and 20", () => {
    expect(setHornCount(EMPTY_FORM, "trumpet", 0).hornCounts).toEqual({ trumpet: 1 });
    expect(setHornCount(EMPTY_FORM, "trumpet", 99).hornCounts).toEqual({ trumpet: 20 });
    expect(setHornCount(EMPTY_FORM, "trumpet", Number.NaN).hornCounts).toEqual({ trumpet: 1 });
  });

  it("builds the request options in catalogue order, with counts above 1 only", () => {
    let state = toggleInstrument(EMPTY_FORM, "trumpet");
    state = toggleInstrument(state, "piano");
    state = setHornCount(state, "trumpet", 2);
    state = setHornCount(state, "tenor sax", 3);
    state = { ...state, otherText: " Organ, , harp ", beatsPerBar: 3 };
    expect(toOptions(state, CATALOGUE)).toEqual({
      instruments: ["piano", "trumpet"],
      horn_counts: { trumpet: 2 },
      other: ["Organ", "harp"],
      beats_per_bar: 3,
    });
  });

  it("needs at least one instrument", () => {
    expect(formError(EMPTY_FORM)).toBe("Choose at least one instrument.");
    expect(formError(toggleInstrument(EMPTY_FORM, "piano"))).toBeNull();
  });

  it("accepts the four upload formats only", () => {
    expect(isAcceptedFile("take.MP3")).toBe(true);
    expect(isAcceptedFile("take.m4a")).toBe(true);
    expect(isAcceptedFile("take.ogg")).toBe(false);
    expect(isAcceptedFile("take")).toBe(false);
  });
});
