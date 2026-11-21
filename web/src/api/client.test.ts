import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createClient } from "./client";

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
  );
}

afterEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("returns the data of a success envelope", async () => {
    const fetcher = respond(200, { success: true, data: { instruments: ["piano"] }, error: null });
    const client = createClient(fetcher);
    await expect(client.catalogue()).resolves.toEqual({ instruments: ["piano"] });
    expect(fetcher).toHaveBeenCalledWith("/api/instruments", undefined);
  });

  it("throws the server message of an error envelope", async () => {
    const client = createClient(respond(400, { success: false, data: null, error: "Unknown instrument 'banjo'" }));
    await expect(client.track("x")).rejects.toThrow(new ApiError("Unknown instrument 'banjo'", 400));
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
    const fetcher = respond(201, { success: true, data: { id: "abc" }, error: null });
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
    const fetcher = respond(200, { success: true, data: { id: "a b" }, error: null });
    await createClient(fetcher).track("a b");
    expect(fetcher).toHaveBeenCalledWith("/api/tracks/a%20b", undefined);
  });
});
