import type { Catalogue, Envelope, JobOptions, Track } from "./types";

const API = "/api";

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
}

export function createClient(fetcher: Fetcher = (input, init) => fetch(input, init)): ApiClient {
  async function call<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response;
    try {
      response = await fetcher(`${API}${path}`, init);
    } catch {
      throw new ApiError("Cannot reach the server. Is jca-serve running?", 0);
    }
    let body: Envelope<T>;
    try {
      body = (await response.json()) as Envelope<T>;
    } catch {
      throw new ApiError(`The server replied ${response.status} without a JSON body`, response.status);
    }
    if (!body.success || body.data === null) {
      throw new ApiError(body.error ?? `The request failed with status ${response.status}`, response.status);
    }
    return body.data;
  }

  return {
    catalogue: () => call<Catalogue>("/instruments"),
    tracks: () => call<readonly Track[]>("/tracks"),
    track: (id) => call<Track>(`/tracks/${encodeURIComponent(id)}`),
    upload: (file, options) => {
      const form = new FormData();
      form.append("file", file);
      form.append("options", JSON.stringify(options));
      return call<Track>("/tracks", { method: "POST", body: form });
    },
  };
}
