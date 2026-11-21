import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App, trackIdFromHash } from "./App";
import type { ApiClient } from "./api/client";
import type { Catalogue, Track } from "./api/types";
import type { AudioService } from "./audio/browserAudio";
import { MixerEngine } from "./audio/engine";

const CATALOGUE: Catalogue = { instruments: ["piano"], horns: [], presets: [] };
const STAGES = ["uploaded", "separating", "tracking", "recognising", "decoded"];

function track(status: Track["status"], done: number, stems: Track["stems"] = []): Track {
  return {
    id: "abc123",
    filename: "take.flac",
    created_at: "2026-11-21T10:00:00.000+00:00",
    status,
    progress: done / 5,
    stages: STAGES.map((name, index) => ({ name, state: index < done ? "done" : "waiting" })),
    warnings: [],
    error: null,
    stems,
  };
}

function client(trackReplies: Track[] = []): ApiClient {
  const getTrack = vi.fn();
  for (const reply of trackReplies) {
    getTrack.mockResolvedValueOnce(reply);
  }
  return {
    catalogue: vi.fn().mockResolvedValue(CATALOGUE),
    tracks: vi.fn().mockResolvedValue([track("done", 5)]),
    track: getTrack,
    upload: vi.fn(),
    chords: vi.fn(() => new Promise<never>(() => undefined)),
    saveEdits: vi.fn(),
    setGrid: vi.fn(),
    evidence: vi.fn(() => new Promise<never>(() => undefined)),
  };
}

function fakeAudio(): AudioService {
  const engine = new MixerEngine({
    currentTime: 0,
    destination: {},
    createGain: () => ({ gain: { value: 1 }, connect: () => undefined }),
    createBufferSource: () => {
      throw new Error("not used");
    },
    resume: async () => undefined,
  });
  return { engine, load: vi.fn(async () => []), stretch: vi.fn(), close: vi.fn() };
}

describe("trackIdFromHash", () => {
  it.each([
    ["#/tracks/abc123", "abc123"],
    ["#/", null],
    ["#/tracks/../x", null],
    ["", null],
  ])("%s gives %s", (hash, id) => {
    expect(trackIdFromHash(hash)).toBe(id);
  });
});

describe("App", () => {
  beforeEach(() => {
    window.location.hash = "";
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows the upload panel and the recent tracks on the home page", async () => {
    render(<App client={client()} createAudio={fakeAudio} />);
    expect(await screen.findByRole("region", { name: "Upload" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "take.flac" })).toHaveAttribute("href", "#/tracks/abc123");
  });

  it("shows an error when the server cannot give the instrument list", async () => {
    const failing = { ...client(), catalogue: vi.fn().mockRejectedValue(new Error("Cannot reach the server")) };
    render(<App client={failing} createAudio={fakeAudio} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });

  it("polls a running track until it is done, and opens the mixer once there are stems", async () => {
    window.location.hash = "#/tracks/abc123";
    const stems: Track["stems"] = [{ name: "piano", kind: "stem", url: "/api/tracks/abc123/stems/piano" }];
    const api = client([track("running", 1), track("running", 2, stems), track("done", 5, stems)]);
    const createAudio = vi.fn(fakeAudio);
    render(<App client={api} createAudio={createAudio} pollMs={10} />);
    // The intermediate states can pass faster than the test reads them, so only the end is checked.
    await vi.waitFor(() => expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100"));
    expect(api.track).toHaveBeenCalledTimes(3);
    expect(createAudio).toHaveBeenCalledTimes(1);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(api.track).toHaveBeenCalledTimes(3);
  });

  it("keeps polling after a failed request and shows its message", async () => {
    window.location.hash = "#/tracks/abc123";
    const api = client();
    vi.mocked(api.track).mockRejectedValueOnce(new Error("Cannot reach the server")).mockResolvedValue(track("done", 5));
    render(<App client={api} createAudio={fakeAudio} pollMs={10} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
    expect(await screen.findByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  });

  it("follows the hash to a track", async () => {
    const api = client([track("done", 5)]);
    render(<App client={api} createAudio={fakeAudio} />);
    await screen.findByRole("region", { name: "Upload" });
    act(() => {
      window.location.hash = "#/tracks/abc123";
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(await screen.findByRole("heading", { name: "take.flac" })).toBeInTheDocument();
  });
});
