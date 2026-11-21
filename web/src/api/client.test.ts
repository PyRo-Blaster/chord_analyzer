import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createClient } from "./client";

const CATALOGUE = { instruments: ["piano"], horns: [], presets: [] };
const TRACK = {
  id: "a b",
  filename: "take.wav",
  created_at: "2026-11-21T10:00:00.000+00:00",
  status: "queued",
  progress: 0,
  stages: [{ name: "uploaded", state: "waiting" }],
  warnings: [],
  error: null,
  stems: [{ name: "piano", kind: "stem", url: "/api/tracks/a%20b/stems/piano" }],
};

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
  );
}

afterEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("returns the checked data of a success envelope", async () => {
    const fetcher = respond(200, { success: true, data: CATALOGUE, error: null });
    await expect(createClient(fetcher).catalogue()).resolves.toEqual(CATALOGUE);
    expect(fetcher).toHaveBeenCalledWith("/api/instruments", undefined);
  });

  it("throws the server message of an error envelope", async () => {
    const client = createClient(respond(400, { success: false, data: null, error: "Unknown instrument 'banjo'" }));
    await expect(client.track("x")).rejects.toThrow(new ApiError("Unknown instrument 'banjo'", 400));
  });

  it("rejects a reply that does not match the schema", async () => {
    const reply = { success: true, data: { ...TRACK, status: "exploded" }, error: null };
    await expect(createClient(respond(200, reply)).track("x")).rejects.toThrow(
      "The server sent an unexpected reply (status)",
    );
  });

  it("rejects a stem link that points away from the API", async () => {
    const stems = [{ name: "piano", kind: "stem", url: "https://example.com/x.flac" }];
    const reply = { success: true, data: [{ ...TRACK, stems }], error: null };
    await expect(createClient(respond(200, reply)).tracks()).rejects.toThrow("stems.0.url");
  });

  it("throws a readable error when the reply is not JSON", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 502 }));
    await expect(createClient(fetcher).tracks()).rejects.toThrow("The server replied 502");
  });

  it("throws a readable error when the server cannot be reached", async () => {
    const fetcher = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(createClient(fetcher).tracks()).rejects.toThrow("Cannot reach the server");
  });

  it("uploads the file and the options as a form", async () => {
    const fetcher = respond(201, { success: true, data: TRACK, error: null });
    const file = new File(["audio"], "take.wav", { type: "audio/wav" });
    const options = { instruments: ["piano"], horn_counts: {}, other: [], beats_per_bar: null };
    await createClient(fetcher).upload(file, options);
    const [url, init] = fetcher.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/tracks");
    expect(init.method).toBe("POST");
    const form = init.body as FormData;
    expect((form.get("file") as File).name).toBe("take.wav");
    expect(JSON.parse(form.get("options") as string)).toEqual(options);
  });

  it("asks for one track by id", async () => {
    const fetcher = respond(200, { success: true, data: TRACK, error: null });
    await expect(createClient(fetcher).track("a b")).resolves.toEqual(TRACK);
    expect(fetcher).toHaveBeenCalledWith("/api/tracks/a%20b", undefined);
  });
});
