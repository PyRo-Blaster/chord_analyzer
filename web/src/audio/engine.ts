/**
 * Plays all stems from one AudioContext clock, so they stay sample-aligned.
 *
 * Positions are in original track seconds. At a speed below 1 the engine plays
 * time-stretched buffers, which are longer by 1 / speed; it maps times both ways.
 */

export const START_LEAD_SECONDS = 0.05; // schedule every start slightly ahead, so all begin together

export interface BufferLike {
  readonly duration: number;
  readonly length: number;
  readonly numberOfChannels: number;
  readonly sampleRate: number;
  getChannelData(channel: number): Float32Array;
}

interface ParamLike {
  value: number;
}

interface NodeLike {
  connect(destination: unknown): unknown;
}

interface SourceLike extends NodeLike {
  buffer: BufferLike | null;
  loop: boolean;
  loopStart: number;
  loopEnd: number;
  // `never` parameters let the real AudioBufferSourceNode handler type fit this one.
  onended: ((this: never, event: never) => unknown) | null;
  start(when: number, offset: number): void;
  stop(): void;
}

interface GainLike extends NodeLike {
  readonly gain: ParamLike;
}

export interface AudioContextLike {
  readonly currentTime: number;
  readonly destination: unknown;
  createBufferSource(): SourceLike;
  createGain(): GainLike;
  resume(): Promise<void>;
}

export interface StemBuffer {
  readonly name: string;
  readonly buffer: BufferLike;
}

export interface LoopRange {
  readonly start: number;
  readonly end: number;
}

interface Channel {
  readonly name: string;
  readonly gain: GainLike;
}

export class MixerEngine {
  onEnded: (() => void) | null = null;

  private readonly context: AudioContextLike;
  private channels: readonly Channel[] = [];
  private buffersBySpeed = new Map<number, Readonly<Record<string, BufferLike>>>();
  private sources: readonly SourceLike[] = [];
  private currentSpeed = 1;
  private loop: LoopRange | null = null;
  private offset = 0; // original seconds where the current playback started
  private startedAt = 0; // context time when it started
  private isPlaying = false;
  private generation = 0; // ended events from stopped sources carry an old generation

  constructor(context: AudioContextLike) {
    this.context = context;
  }

  get playing(): boolean {
    return this.isPlaying;
  }

  get speed(): number {
    return this.currentSpeed;
  }

  get duration(): number {
    const first = Object.values(this.buffersBySpeed.get(1) ?? {})[0];
    return first?.duration ?? 0;
  }

  setStems(stems: readonly StemBuffer[]): void {
    this.stopSources();
    this.channels = stems.map((stem) => {
      const gain = this.context.createGain();
      gain.connect(this.context.destination);
      return { name: stem.name, gain };
    });
    this.buffersBySpeed = new Map([[1, Object.fromEntries(stems.map((stem) => [stem.name, stem.buffer]))]]);
    this.currentSpeed = 1;
    this.offset = 0;
  }

  setStretched(speed: number, buffers: Readonly<Record<string, BufferLike>>): void {
    this.buffersBySpeed = new Map([...this.buffersBySpeed, [speed, buffers]]);
  }

  hasSpeed(speed: number): boolean {
    return this.buffersBySpeed.has(speed);
  }

  setSpeed(speed: number): void {
    if (!this.buffersBySpeed.has(speed)) {
      throw new Error(`No stretched audio for speed ${speed}`);
    }
    this.restartWith(() => {
      this.currentSpeed = speed;
    });
  }

  setGains(gains: Readonly<Record<string, number>>): void {
    for (const channel of this.channels) {
      channel.gain.gain.value = gains[channel.name] ?? 0;
    }
  }

  setLoop(range: LoopRange | null): void {
    if (range !== null && !(range.end > range.start)) {
      throw new RangeError("A loop must end after it starts");
    }
    this.restartWith(() => {
      this.loop = range;
    });
  }

  position(): number {
    if (!this.isPlaying) {
      return this.offset;
    }
    const elapsed = Math.max(0, this.context.currentTime - this.startedAt) * this.currentSpeed;
    const raw = this.offset + elapsed;
    if (this.loop !== null && raw >= this.loop.end) {
      const length = this.loop.end - this.loop.start;
      return this.loop.start + ((raw - this.loop.start) % length);
    }
    return Math.min(raw, this.duration);
  }

  seek(seconds: number): void {
    this.restartWith(() => {
      this.offset = Math.min(Math.max(0, seconds), this.duration);
    });
  }

  play(): void {
    if (this.isPlaying || this.channels.length === 0) {
      return;
    }
    void this.context.resume();
    const buffers = this.buffersBySpeed.get(this.currentSpeed) ?? {};
    const insideLoop = this.loop === null || (this.offset >= this.loop.start && this.offset < this.loop.end);
    this.offset = insideLoop ? this.offset : (this.loop?.start ?? 0);
    this.startedAt = this.context.currentTime + START_LEAD_SECONDS;
    this.generation += 1;
    const generation = this.generation;
    this.sources = this.channels.map((channel) => {
      const source = this.context.createBufferSource();
      source.buffer = buffers[channel.name] ?? null;
      if (this.loop !== null) {
        source.loop = true;
        source.loopStart = this.loop.start / this.currentSpeed;
        source.loopEnd = this.loop.end / this.currentSpeed;
      }
      source.connect(channel.gain);
      source.start(this.startedAt, this.offset / this.currentSpeed);
      return source;
    });
    const first = this.sources[0];
    if (first !== undefined) {
      first.onended = () => this.handleEnded(generation);
    }
    this.isPlaying = true;
  }

  pause(): void {
    if (!this.isPlaying) {
      return;
    }
    this.offset = this.position();
    this.stopSources();
  }

  private handleEnded(generation: number): void {
    if (generation !== this.generation || !this.isPlaying) {
      return;
    }
    this.stopSources();
    this.offset = this.duration;
    this.onEnded?.();
  }

  private restartWith(change: () => void): void {
    const wasPlaying = this.isPlaying;
    this.pause();
    change();
    if (wasPlaying) {
      this.play();
    }
  }

  private stopSources(): void {
    this.generation += 1;
    for (const source of this.sources) {
      source.onended = null;
      source.stop();
    }
    this.sources = [];
    this.isPlaying = false;
  }
}
