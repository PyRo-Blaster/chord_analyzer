export type JobStatus = "queued" | "running" | "done" | "failed";
export type StageState = "waiting" | "running" | "done" | "failed";
export type StemKind = "stem" | "residue";

export interface Envelope<T> {
  readonly success: boolean;
  readonly data: T | null;
  readonly error: string | null;
}

export interface Preset {
  readonly id: string;
  readonly label: string;
  readonly instruments: readonly string[];
  readonly horn_counts: Readonly<Record<string, number>>;
}

export interface Catalogue {
  readonly instruments: readonly string[];
  readonly horns: readonly string[];
  readonly presets: readonly Preset[];
}

export interface JobOptions {
  readonly instruments: readonly string[];
  readonly horn_counts: Readonly<Record<string, number>>;
  readonly other: readonly string[];
  readonly beats_per_bar: number | null;
}

export interface StageView {
  readonly name: string;
  readonly state: StageState;
}

export interface StemView {
  readonly name: string;
  readonly kind: StemKind;
  readonly url: string;
}

export interface Track {
  readonly id: string;
  readonly filename: string;
  readonly created_at: string;
  readonly status: JobStatus;
  readonly progress: number;
  readonly stages: readonly StageView[];
  readonly warnings: readonly string[];
  readonly error: string | null;
  readonly stems: readonly StemView[];
}
