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
