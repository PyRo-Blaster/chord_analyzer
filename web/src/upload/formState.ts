import type { Catalogue, JobOptions } from "../api/types";

export const ACCEPTED_EXTENSIONS = [".mp3", ".wav", ".flac", ".m4a"] as const;
export const MIN_HORN_COUNT = 1;
export const MAX_HORN_COUNT = 20;

export interface FormState {
  readonly selected: readonly string[];
  readonly hornCounts: Readonly<Record<string, number>>;
  readonly otherText: string;
  readonly beatsPerBar: number | null;
  readonly presetId: string | null;
}

export const EMPTY_FORM: FormState = {
  selected: [],
  hornCounts: {},
  otherText: "",
  beatsPerBar: null,
  presetId: null,
};

export function applyPreset(state: FormState, catalogue: Catalogue, presetId: string): FormState {
  const preset = catalogue.presets.find((candidate) => candidate.id === presetId);
  if (preset === undefined) {
    return state;
  }
  return { ...state, selected: [...preset.instruments], hornCounts: { ...preset.horn_counts }, presetId };
}

export function toggleInstrument(state: FormState, name: string): FormState {
  const isSelected = state.selected.includes(name);
  const selected = isSelected ? state.selected.filter((item) => item !== name) : [...state.selected, name];
  const hornCounts = isSelected ? withoutKey(state.hornCounts, name) : state.hornCounts;
  return { ...state, selected, hornCounts, presetId: null };
}

export function setHornCount(state: FormState, name: string, count: number): FormState {
  const whole = Number.isFinite(count) ? Math.round(count) : MIN_HORN_COUNT;
  const clamped = Math.min(MAX_HORN_COUNT, Math.max(MIN_HORN_COUNT, whole));
  return { ...state, hornCounts: { ...state.hornCounts, [name]: clamped } };
}

export function toOptions(state: FormState, catalogue: Catalogue): JobOptions {
  const instruments = catalogue.instruments.filter((name) => state.selected.includes(name));
  const hornCounts = Object.fromEntries(
    Object.entries(state.hornCounts).filter(([name, count]) => state.selected.includes(name) && count > 1),
  );
  const other = state.otherText
    .split(",")
    .map((name) => name.trim())
    .filter((name) => name.length > 0);
  return { instruments, horn_counts: hornCounts, other, beats_per_bar: state.beatsPerBar };
}

export function formError(state: FormState): string | null {
  return state.selected.length === 0 && state.otherText.trim() === "" ? "Choose at least one instrument." : null;
}

export function isAcceptedFile(name: string): boolean {
  const lower = name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((extension) => lower.endsWith(extension));
}

function withoutKey(record: Readonly<Record<string, number>>, key: string): Record<string, number> {
  return Object.fromEntries(Object.entries(record).filter(([name]) => name !== key));
}
