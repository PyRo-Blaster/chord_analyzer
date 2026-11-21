import type { z } from "zod";
import { CatalogueSchema, ChordViewSchema, EvidenceSchema, TrackSchema } from "./types";
import type {
  Catalogue,
  ChartEdit,
  ChordView,
  Envelope,
  Evidence,
  EvidenceSource,
  ExportFormat,
  GridView,
  JobOptions,
  Track,
} from "./types";

const API = "/api";
const TrackListSchema = TrackSchema.array();

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type Fetcher = (input: string, init?: RequestInit) => Promise<Response>;

export interface ApiClient {
  catalogue(): Promise<Catalogue>;
  tracks(): Promise<readonly Track[]>;
  track(id: string): Promise<Track>;
  upload(file: File, options: JobOptions): Promise<Track>;
  chords(id: string): Promise<ChordView>;
  saveEdits(id: string, edits: readonly ChartEdit[]): Promise<ChordView>;
  setGrid(id: string, grid: GridView): Promise<Track>;
  evidence(id: string, source: EvidenceSource): Promise<Evidence>;
}

export function exportUrl(id: string, format: ExportFormat): string {
  return `${API}/tracks/${encodeURIComponent(id)}/export?format=${format}`;
}

export function createClient(fetcher: Fetcher = (input, init) => fetch(input, init)): ApiClient {
  async function call<S extends z.ZodType>(path: string, schema: S, init?: RequestInit): Promise<z.infer<S>> {
    let response: Response;
    try {
      response = await fetcher(`${API}${path}`, init);
    } catch {
      throw new ApiError("Cannot reach the server. Is jca-serve running?", 0);
    }
    let body: Envelope;
    try {
      body = (await response.json()) as Envelope;
    } catch {
      throw new ApiError(`The server replied ${response.status} without a JSON body`, response.status);
    }
    if (!body.success) {
      throw new ApiError(body.error ?? `The request failed with status ${response.status}`, response.status);
    }
    const parsed = schema.safeParse(body.data);
    if (!parsed.success) {
      const where = parsed.error.issues[0]?.path.join(".") || "reply";
      throw new ApiError(`The server sent an unexpected reply (${where})`, response.status);
    }
    return parsed.data;
  }

  return {
    catalogue: () => call("/instruments", CatalogueSchema),
    tracks: () => call("/tracks", TrackListSchema),
    track: (id) => call(`/tracks/${encodeURIComponent(id)}`, TrackSchema),
    upload: (file, options) => {
      const form = new FormData();
      form.append("file", file);
      form.append("options", JSON.stringify(options));
      return call("/tracks", TrackSchema, { method: "POST", body: form });
    },
    chords: (id) => call(`/tracks/${encodeURIComponent(id)}/chords`, ChordViewSchema),
    saveEdits: (id, edits) => call(`/tracks/${encodeURIComponent(id)}/chart`, ChordViewSchema, json("PATCH", { edits })),
    setGrid: (id, grid) => call(`/tracks/${encodeURIComponent(id)}/grid`, TrackSchema, json("PATCH", grid)),
    evidence: (id, source) =>
      call(`/tracks/${encodeURIComponent(id)}/evidence?source=${source}`, EvidenceSchema),
  };
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}
