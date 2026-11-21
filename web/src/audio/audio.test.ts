import { describe, expect, it } from "vitest";
import { defaultLanes, effectiveGains, setGain, toggleMute, toggleSolo } from "./mixState";
import { computePeaks } from "./peaks";
import { WSOLA, computePositions, renderWithPositions, stretchStems } from "./wsola";

const RATE = 44100;

function sine(frequency: number, seconds: number, amplitude = 0.5): Float32Array {
  const samples = new Float32Array(Math.round(seconds * RATE));
  for (let index = 0; index < samples.length; index += 1) {
    samples[index] = amplitude * Math.sin((2 * Math.PI * frequency * index) / RATE);
  }
  return samples;
}

function dominantFrequency(samples: Float32Array): number {
  const start = Math.floor(samples.length * 0.2);
  const end = Math.floor(samples.length * 0.8);
  let crossings = 0;
  for (let index = start + 1; index < end; index += 1) {
    if ((samples[index - 1] ?? 0) < 0 && (samples[index] ?? 0) >= 0) {
      crossings += 1;
    }
  }
  return crossings / ((end - start) / RATE);
}

describe("mix state", () => {
  const lanes = defaultLanes([
    { name: "piano", kind: "stem" },
    { name: "drums", kind: "stem" },
    { name: "residue", kind: "residue" },
  ]);

  it("plays every lane at full volume by default, which together is the full mix", () => {
    expect(effectiveGains(lanes)).toEqual({ piano: 1, drums: 1, residue: 1 });
  });

  it("silences a muted lane", () => {
    expect(effectiveGains(toggleMute(lanes, "drums"))).toEqual({ piano: 1, drums: 0, residue: 1 });
  });

  it("plays only soloed lanes when any lane is soloed", () => {
    const soloed = toggleSolo(toggleSolo(lanes, "piano"), "residue");
    expect(effectiveGains(soloed)).toEqual({ piano: 1, drums: 0, residue: 1 });
    expect(effectiveGains(toggleSolo(soloed, "piano"))).toEqual({ piano: 0, drums: 0, residue: 1 });
  });

  it("keeps mute stronger than solo", () => {
    expect(effectiveGains(toggleMute(toggleSolo(lanes, "piano"), "piano")).piano).toBe(0);
  });

  it("clamps the volume and leaves the old lanes alone", () => {
    const louder = setGain(lanes, "piano", 3);
    expect(effectiveGains(setGain(lanes, "piano", 0.25)).piano).toBe(0.25);
    expect(louder.find((lane) => lane.name === "piano")?.gain).toBe(1);
    expect(setGain(lanes, "piano", -1).find((lane) => lane.name === "piano")?.gain).toBe(0);
    expect(lanes.find((lane) => lane.name === "piano")?.gain).toBe(1);
  });
});

describe("peaks", () => {
  it("returns the loudest sample of each bucket across channels", () => {
    const left = new Float32Array([0.1, -0.5, 0.2, 0.0]);
    const right = new Float32Array([0.0, 0.1, -0.9, 0.3]);
    expect(Array.from(computePeaks([left, right], 2))).toEqual([
      expect.closeTo(0.5, 5),
      expect.closeTo(0.9, 5),
    ]);
  });

  it("handles more buckets than samples and empty audio", () => {
    expect(computePeaks([new Float32Array([0.5])], 4)).toHaveLength(4);
    expect(Array.from(computePeaks([new Float32Array(0)], 3))).toEqual([0, 0, 0]);
  });
});

describe("WSOLA time-stretch", () => {
  it("makes the audio longer by one over the speed", () => {
    const input = sine(440, 2);
    const output = renderWithPositions(input, computePositions(input, 0.75));
    expect(output.length).toBeGreaterThan(input.length / 0.75 - WSOLA.frame);
    expect(output.length).toBeLessThan(input.length / 0.75 + WSOLA.frame);
  });

  it.each([0.5, 0.75, 1])("keeps the pitch at speed %s", (speed) => {
    const input = sine(440, 2);
    const output = renderWithPositions(input, computePositions(input, speed));
    expect(dominantFrequency(output)).toBeGreaterThan(440 * 0.98);
    expect(dominantFrequency(output)).toBeLessThan(440 * 1.02);
  });

  it("leaves the audio unchanged at full speed, away from the edges", () => {
    const input = sine(220, 1);
    const output = renderWithPositions(input, computePositions(input, 1));
    for (let index = WSOLA.frame; index < input.length - WSOLA.frame; index += 997) {
      expect(output[index]).toBeCloseTo(input[index] ?? 0, 4);
    }
  });

  it("stretches all stems with the same offsets, so they still add up to the mix", () => {
    const piano = [sine(440, 1.5, 0.3), sine(440, 1.5, 0.3)];
    const bass = [sine(110, 1.5, 0.4), sine(110, 1.5, 0.4)];
    const [stretchedPiano, stretchedBass] = stretchStems([piano, bass], 0.6);
    const mix = (piano[0] as Float32Array).map((value, index) => value + (bass[0]?.[index] ?? 0));
    const stretchedMix = renderWithPositions(mix, computePositions(mix, 0.6));
    const left = stretchedPiano?.[0] as Float32Array;
    expect(left.length).toBe(stretchedBass?.[0]?.length);
    for (let index = 0; index < left.length; index += 1009) {
      expect(left[index]! + stretchedBass![0]![index]!).toBeCloseTo(stretchedMix[index]!, 5);
    }
  });

  it("rejects a speed outside 0.25 to 1", () => {
    expect(() => computePositions(new Float32Array(10), 0)).toThrow("speed");
    expect(() => computePositions(new Float32Array(10), 1.5)).toThrow("speed");
  });

  it("returns silence for audio shorter than one frame", () => {
    const output = renderWithPositions(new Float32Array(100), computePositions(new Float32Array(100), 0.5));
    expect(output.every((value) => value === 0)).toBe(true);
  });
});
