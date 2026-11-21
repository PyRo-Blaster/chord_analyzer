import type { StemView } from "../api/types";
import type { BufferLike, StemBuffer } from "./engine";
import { MixerEngine } from "./engine";
import type { StretchReply, StretchRequest } from "./stretchWorker";

export const SAMPLE_RATE = 44100; // the stems' rate: no resampling on decode

/** What the mixer needs from the browser. Tests pass a fake. */
export interface AudioService {
  readonly engine: MixerEngine;
  load(stems: readonly StemView[]): Promise<readonly StemBuffer[]>;
  stretch(speed: number, stems: readonly StemBuffer[]): Promise<Readonly<Record<string, BufferLike>>>;
  close(): void;
}

export function createBrowserAudio(): AudioService {
  const context = new AudioContext({ sampleRate: SAMPLE_RATE, latencyHint: "playback" });
  const worker = new Worker(new URL("./stretchWorker.ts", import.meta.url), { type: "module" });
  const pending = new Map<number, (reply: StretchReply) => void>();
  let nextId = 0;
  worker.onmessage = (event: MessageEvent<StretchReply>) => {
    pending.get(event.data.id)?.(event.data);
    pending.delete(event.data.id);
  };

  async function decode(stem: StemView): Promise<StemBuffer> {
    const response = await fetch(stem.url);
    if (!response.ok) {
      throw new Error(`Could not load the ${stem.name} stem (status ${response.status})`);
    }
    return { name: stem.name, buffer: await context.decodeAudioData(await response.arrayBuffer()) };
  }

  return {
    engine: new MixerEngine(context),
    load: (stems) => Promise.all(stems.map(decode)),
    stretch: (speed, stems) =>
      new Promise((resolve, reject) => {
        const id = nextId;
        nextId += 1;
        const channels = stems.map(({ buffer }) =>
          Array.from({ length: buffer.numberOfChannels }, (_, index) => buffer.getChannelData(index).slice()),
        );
        pending.set(id, (reply) => {
          if (reply.stems === undefined) {
            reject(new Error(reply.error ?? "The time-stretch failed"));
            return;
          }
          const buffers = reply.stems.map((stem) => {
            const buffer = context.createBuffer(stem.length, stem[0]?.length ?? 1, SAMPLE_RATE);
            stem.forEach((channel, index) => buffer.copyToChannel(channel as Float32Array<ArrayBuffer>, index));
            return buffer;
          });
          resolve(Object.fromEntries(stems.map((stem, index) => [stem.name, buffers[index] as BufferLike])));
        });
        const request: StretchRequest = { id, speed, stems: channels };
        worker.postMessage(request, channels.flat().map((channel) => channel.buffer));
      }),
    close: () => {
      worker.terminate();
      void context.close();
    },
  };
}
