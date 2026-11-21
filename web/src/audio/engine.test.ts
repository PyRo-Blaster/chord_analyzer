import { beforeEach, describe, expect, it } from "vitest";
import type { AudioContextLike, BufferLike } from "./engine";
import { MixerEngine, START_LEAD_SECONDS } from "./engine";

class FakeBuffer implements BufferLike {
  constructor(
    readonly duration: number,
    readonly label = "",
  ) {}
  readonly numberOfChannels = 2;
  readonly sampleRate = 44100;
  get length() {
    return Math.round(this.duration * this.sampleRate);
  }
  getChannelData() {
    return new Float32Array(this.length);
  }
}

class FakeSource {
  buffer: BufferLike | null = null;
  loop = false;
  loopStart = 0;
  loopEnd = 0;
  onended: (() => void) | null = null;
  started: [number, number] | null = null;
  stopped = false;
  connect() {
    return this;
  }
  start(when: number, offset: number) {
    this.started = [when, offset];
  }
  stop() {
    this.stopped = true;
  }
}

class FakeGain {
  readonly gain = { value: 1 };
  connect() {
    return this;
  }
}

class FakeContext implements AudioContextLike {
  currentTime = 10;
  readonly destination = {};
  readonly sources: FakeSource[] = [];
  readonly gains: FakeGain[] = [];
  resumed = 0;
  createBufferSource() {
    const source = new FakeSource();
    this.sources.push(source);
    return source;
  }
  createGain() {
    const gain = new FakeGain();
    this.gains.push(gain);
    return gain;
  }
  async resume() {
    this.resumed += 1;
  }
}

describe("MixerEngine", () => {
  let context: FakeContext;
  let engine: MixerEngine;

  beforeEach(() => {
    context = new FakeContext();
    engine = new MixerEngine(context);
    engine.setStems([
      { name: "piano", buffer: new FakeBuffer(60) },
      { name: "bass", buffer: new FakeBuffer(60) },
    ]);
  });

  it("starts every stem at the same moment and offset", () => {
    engine.seek(12);
    engine.play();
    const starts = context.sources.map((source) => source.started);
    expect(starts).toEqual([
      [10 + START_LEAD_SECONDS, 12],
      [10 + START_LEAD_SECONDS, 12],
    ]);
    expect(engine.playing).toBe(true);
    expect(context.resumed).toBe(1);
  });

  it("reports the position from the shared clock", () => {
    engine.play();
    context.currentTime = 10 + START_LEAD_SECONDS + 3.5;
    expect(engine.position()).toBeCloseTo(3.5);
  });

  it("keeps the position when paused and stops every source", () => {
    engine.play();
    context.currentTime = 10 + START_LEAD_SECONDS + 5;
    engine.pause();
    expect(engine.playing).toBe(false);
    expect(engine.position()).toBeCloseTo(5);
    expect(context.sources.every((source) => source.stopped)).toBe(true);
  });

  it("restarts all sources when seeking during playback", () => {
    engine.play();
    engine.seek(30);
    const latest = context.sources.slice(-2);
    expect(latest.map((source) => source.started?.[1])).toEqual([30, 30]);
    expect(context.sources.slice(0, 2).every((source) => source.stopped)).toBe(true);
  });

  it("keeps a seek inside the track", () => {
    engine.seek(-4);
    expect(engine.position()).toBe(0);
    engine.seek(99);
    expect(engine.position()).toBe(60);
  });

  it("sets the gain of each stem", () => {
    engine.setGains({ piano: 0, bass: 0.5 });
    expect(context.gains.map((gain) => gain.gain.value)).toEqual([0, 0.5]);
  });

  it("loops a range and wraps the position inside it", () => {
    engine.setLoop({ start: 8, end: 12 });
    engine.seek(2);
    engine.play();
    const source = context.sources[0] as FakeSource;
    expect([source.loop, source.loopStart, source.loopEnd, source.started?.[1]]).toEqual([true, 8, 12, 8]);
    context.currentTime = 10 + START_LEAD_SECONDS + 5;
    expect(engine.position()).toBeCloseTo(9);
  });

  it("rejects an empty loop", () => {
    expect(() => engine.setLoop({ start: 5, end: 5 })).toThrow("loop");
  });

  it("plays stretched buffers at a lower speed and maps the time back", () => {
    engine.setStretched(0.5, { piano: new FakeBuffer(120), bass: new FakeBuffer(120) });
    engine.seek(10);
    engine.setSpeed(0.5);
    engine.play();
    expect(context.sources.at(-1)?.started?.[1]).toBeCloseTo(20);
    context.currentTime = 10 + START_LEAD_SECONDS + 4;
    expect(engine.position()).toBeCloseTo(12);
    expect(engine.speed).toBe(0.5);
  });

  it("needs stretched buffers before switching speed", () => {
    expect(() => engine.setSpeed(0.75)).toThrow("No stretched audio for speed 0.75");
  });

  it("stops at the end of the track and tells the listener", () => {
    let ended = 0;
    engine.onEnded = () => {
      ended += 1;
    };
    engine.play();
    (context.sources[0] as FakeSource).onended?.();
    expect(engine.playing).toBe(false);
    expect(engine.position()).toBe(60);
    expect(ended).toBe(1);
  });

  it("ignores the ended event of a source it stopped itself", () => {
    engine.play();
    const first = context.sources[0] as FakeSource;
    engine.pause();
    first.onended?.();
    expect(engine.position()).toBe(0);
  });

  it("does nothing when played without stems", () => {
    const empty = new MixerEngine(new FakeContext());
    empty.play();
    expect(empty.playing).toBe(false);
    expect(empty.duration).toBe(0);
  });
});
