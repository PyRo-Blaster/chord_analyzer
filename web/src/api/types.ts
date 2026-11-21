import { z } from "zod";

// Every API reply is checked against these schemas: data from the server is not trusted.

export const JobStatusSchema = z.enum(["queued", "running", "done", "failed"]);
export const StageStateSchema = z.enum(["waiting", "running", "done", "failed"]);

export const PresetSchema = z.object({
  id: z.string(),
  label: z.string(),
  instruments: z.array(z.string()),
  horn_counts: z.record(z.string(), z.number().int().positive()),
});

export const CatalogueSchema = z.object({
  instruments: z.array(z.string()).min(1),
  horns: z.array(z.string()),
  presets: z.array(PresetSchema),
});

export const StageViewSchema = z.object({ name: z.string(), state: StageStateSchema });

export const StemViewSchema = z.object({
  name: z.string().min(1),
  kind: z.enum(["stem", "residue"]),
  url: z.string().startsWith("/api/"),
});

export const TrackSchema = z.object({
  id: z.string().min(1),
  filename: z.string(),
  created_at: z.string(),
  status: JobStatusSchema,
  progress: z.number().min(0).max(1),
  stages: z.array(StageViewSchema),
  warnings: z.array(z.string()),
  error: z.string().nullable(),
  stems: z.array(StemViewSchema),
});

export type JobStatus = z.infer<typeof JobStatusSchema>;
export type StageState = z.infer<typeof StageStateSchema>;
export type Preset = Readonly<z.infer<typeof PresetSchema>>;
export type Catalogue = Readonly<z.infer<typeof CatalogueSchema>>;
export type StageView = Readonly<z.infer<typeof StageViewSchema>>;
export type StemView = Readonly<z.infer<typeof StemViewSchema>>;
export type Track = Readonly<z.infer<typeof TrackSchema>>;

export interface Envelope {
  readonly success: boolean;
  readonly data: unknown;
  readonly error: string | null;
}

export interface JobOptions {
  readonly instruments: readonly string[];
  readonly horn_counts: Readonly<Record<string, number>>;
  readonly other: readonly string[];
  readonly beats_per_bar: number | null;
}

export const Jazz5Schema = z.enum(["maj", "min", "dom7", "hdim7", "dim"]);

export const ChordPartsSchema = z.object({
  root: z.string().nullable(),
  class: Jazz5Schema.nullable(),
  extensions: z.array(z.string()),
  bass: z.string().nullable(),
});

const TierSchema = z.object({ symbol: z.string(), tier1: z.string(), tier2: z.string() });
export const LabelViewSchema = TierSchema.extend({ label: z.string() });
export const PartsViewSchema = TierSchema.extend({ parts: ChordPartsSchema });

export const BeatViewSchema = z.object({
  index: z.number().int().nonnegative(),
  bar: z.number().int().nonnegative(),
  beat: z.number().int().positive(),
  time: z.number().nonnegative(),
  agreement: z.enum(["A", "B", "C", "D"]),
  needs_review: z.boolean(),
  confidence: z.number().min(0).max(1),
  extensions_confidence: z.number().min(0).max(1),
  bass_pitch_class: z.string().nullable(),
  lv_chordia: LabelViewSchema,
  btc: LabelViewSchema,
  draft: PartsViewSchema,
  user_edit: PartsViewSchema.nullable(),
});

export const GridViewSchema = z.object({
  beats_per_bar: z.number().int().positive().nullable(),
  first_downbeat_index: z.number().int().nonnegative().nullable(),
  tempo_bpm: z.number().positive().nullable(),
  first_beat_time: z.number().nonnegative().nullable(),
});

export const ChordViewSchema = z.object({
  beats: z.array(BeatViewSchema),
  duration: z.number().nonnegative(),
  unplaced_edits: z.number().int().nonnegative(),
  grid: GridViewSchema,
});

export const EvidenceSchema = z.object({
  source: z.enum(["mix", "piano", "bass"]),
  profiles: z.array(z.array(z.number().min(0).max(1)).length(12)),
});

export type Jazz5 = z.infer<typeof Jazz5Schema>;
export type ChordParts = Readonly<z.infer<typeof ChordPartsSchema>>;
export type PartsView = Readonly<z.infer<typeof PartsViewSchema>>;
export type LabelView = Readonly<z.infer<typeof LabelViewSchema>>;
export type BeatView = Readonly<z.infer<typeof BeatViewSchema>>;
export type GridView = Readonly<z.infer<typeof GridViewSchema>>;
export type ChordView = Readonly<z.infer<typeof ChordViewSchema>>;
export type EvidenceSource = z.infer<typeof EvidenceSchema>["source"];
export type Evidence = Readonly<z.infer<typeof EvidenceSchema>>;
export type ExportFormat = "text" | "json" | "stems";

export interface ChartEdit {
  readonly time: number;
  readonly user_edit: ChordParts | null;
}
