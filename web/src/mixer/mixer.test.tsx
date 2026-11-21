import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { StemView } from "../api/types";
import type { AudioService } from "../audio/browserAudio";
import type { BufferLike, StemBuffer } from "../audio/engine";
import { MixerEngine } from "../audio/engine";
import { Mixer } from "./Mixer";
import { formatTime } from "./Transport";

const STEMS: StemView[] = [
  { name: "piano", kind: "stem", url: "/api/tracks/t1/stems/piano" },
  { name: "double bass", kind: "stem", url: "/api/tracks/t1/stems/double%20bass" },
  { name: "residue", kind: "residue", url: "/api/tracks/t1/stems/residue" },
];

function buffer(duration: number): BufferLike {
  const length = Math.round(duration * 100);
  return {
    duration,
    length,
    numberOfChannels: 1,
    sampleRate: 100,
    getChannelData: () => Float32Array.from({ length }, (_, index) => Math.sin(index / 5)),
  };
}

class FakeContext {
  currentTime = 0;
  readonly destination = {};
  readonly gains: { gain: { value: number } }[] = [];
  createGain() {
    const node = { gain: { value: 1 }, connect: () => node };
    this.gains.push(node);
    return node;
  }
  createBufferSource() {
    return {
      buffer: null,
      loop: false,
      loopStart: 0,
      loopEnd: 0,
      onended: null,
      connect: () => undefined,
      start: () => undefined,
      stop: () => undefined,
    };
  }
  resume = async () => undefined;
}

function fakeAudio(overrides: Partial<AudioService> = {}) {
  const context = new FakeContext();
  const engine = new MixerEngine(context);
  const stretch = vi.fn(async (speed: number, stems: readonly StemBuffer[]) =>
    Object.fromEntries(stems.map((stem) => [stem.name, buffer(stem.buffer.duration / speed)])),
  );
  const service: AudioService = {
    engine,
    load: vi.fn(async (stems: readonly StemView[]) => stems.map((stem) => ({ name: stem.name, buffer: buffer(60) }))),
    stretch,
    close: vi.fn(),
    ...overrides,
  };
  return { service, engine, context, stretch };
}

async function renderMixer(audio = fakeAudio()) {
  render(<Mixer stems={STEMS} trackName="take" audio={audio.service} />);
  await screen.findByRole("group", { name: "piano" });
  return audio;
}

describe("Mixer", () => {
  it("shows one lane for each stem and the residue, with a download link", async () => {
    await renderMixer();
    const lanes = screen.getAllByRole("group").filter((element) => element.classList.contains("lane"));
    expect(lanes.map((lane) => lane.getAttribute("aria-label"))).toEqual(["piano", "double bass", "residue"]);
    const download = within(screen.getByRole("group", { name: "double bass" })).getByRole("link", {
      name: "Download",
    });
    expect(download).toHaveAttribute("href", "/api/tracks/t1/stems/double%20bass?download=1");
    expect(screen.getByRole("group", { name: "residue" })).toHaveClass("residue");
  });

  it("mutes and solos lanes through the engine gains", async () => {
    const { context } = await renderMixer();
    await userEvent.click(within(screen.getByRole("group", { name: "piano" })).getByRole("button", { name: "Mute" }));
    expect(context.gains.map((gain) => gain.gain.value)).toEqual([0, 1, 1]);
    await userEvent.click(
      within(screen.getByRole("group", { name: "double bass" })).getByRole("button", { name: "Solo" }),
    );
    expect(context.gains.map((gain) => gain.gain.value)).toEqual([0, 1, 0]);
  });

  it("changes a lane volume", async () => {
    const { context } = await renderMixer();
    const slider = within(screen.getByRole("group", { name: "residue" })).getByRole("slider", { name: "Volume" });
    act(() => {
      fireEvent.change(slider, { target: { value: "0.25" } });
    });
    expect(context.gains[2]?.gain.value).toBe(0.25);
  });

  it("plays and pauses", async () => {
    const { engine } = await renderMixer();
    await userEvent.click(screen.getByRole("button", { name: "Play" }));
    expect(engine.playing).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Pause" }));
    expect(engine.playing).toBe(false);
    expect(screen.getByText("0:00 / 1:00")).toBeInTheDocument();
  });

  it("stretches the stems once for each new speed", async () => {
    const audio = await renderMixer();
    const speed = screen.getByLabelText("Speed");
    await userEvent.selectOptions(speed, "0.75");
    await vi.waitFor(() => expect(audio.engine.speed).toBe(0.75));
    expect(audio.stretch).toHaveBeenCalledTimes(1);
    await userEvent.selectOptions(speed, "1");
    await userEvent.selectOptions(speed, "0.75");
    await vi.waitFor(() => expect(audio.engine.speed).toBe(0.75));
    expect(audio.stretch).toHaveBeenCalledTimes(1);
  });

  it("shows an error when the stretch fails and keeps the old speed", async () => {
    const audio = fakeAudio({ stretch: vi.fn().mockRejectedValue(new Error("out of memory")) });
    await renderMixer(audio);
    await userEvent.selectOptions(screen.getByLabelText("Speed"), "0.5");
    expect(await screen.findByRole("alert")).toHaveTextContent("out of memory");
    expect(audio.engine.speed).toBe(1);
  });

  it("sets a loop from the cursor position and clears it", async () => {
    const { engine } = await renderMixer();
    const setLoop = vi.spyOn(engine, "setLoop");
    engine.seek(10);
    await userEvent.click(screen.getByRole("button", { name: "Loop start" }));
    engine.seek(14);
    await userEvent.click(screen.getByRole("button", { name: "Loop end" }));
    expect(setLoop).toHaveBeenLastCalledWith({ start: 10, end: 14 });
    expect(screen.getByText("Loop 0:10 – 0:14")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear loop" }));
    expect(setLoop).toHaveBeenLastCalledWith(null);
  });

  it("seeks when a waveform is clicked", async () => {
    const { engine } = await renderMixer();
    const wave = within(screen.getByRole("group", { name: "piano" })).getByTestId("wave");
    vi.spyOn(wave, "getBoundingClientRect").mockReturnValue({ left: 0, width: 200 } as DOMRect);
    await userEvent.pointer({ keys: "[MouseLeft]", target: wave, coords: { clientX: 50 } });
    expect(engine.position()).toBeCloseTo(15);
  });

  it("shows an error when the stems cannot be loaded", async () => {
    const audio = fakeAudio({ load: vi.fn().mockRejectedValue(new Error("Could not load the piano stem")) });
    render(<Mixer stems={STEMS} trackName="take" audio={audio.service} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load the piano stem");
  });

  it("closes the audio when it goes away", async () => {
    const audio = fakeAudio();
    const { unmount } = render(<Mixer stems={STEMS} trackName="take" audio={audio.service} />);
    await screen.findByRole("group", { name: "piano" });
    unmount();
    expect(audio.service.close).toHaveBeenCalled();
  });
});

describe("formatTime", () => {
  it.each([
    [0, "0:00"],
    [9.6, "0:09"],
    [75, "1:15"],
    [3600, "60:00"],
  ])("%s seconds is %s", (seconds, text) => {
    expect(formatTime(seconds)).toBe(text);
  });
});
