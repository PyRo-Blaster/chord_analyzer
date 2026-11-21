/// <reference lib="webworker" />
import { stretchStems } from "./wsola";

export interface StretchRequest {
  readonly id: number;
  readonly speed: number;
  readonly stems: readonly (readonly Float32Array[])[];
}

export interface StretchReply {
  readonly id: number;
  readonly stems?: Float32Array[][];
  readonly error?: string;
}

self.onmessage = (event: MessageEvent<StretchRequest>) => {
  const { id, speed, stems } = event.data;
  try {
    const stretched = stretchStems(stems, speed);
    const reply: StretchReply = { id, stems: stretched };
    self.postMessage(reply, stretched.flat().map((channel) => channel.buffer as ArrayBuffer));
  } catch (error) {
    const reply: StretchReply = { id, error: error instanceof Error ? error.message : String(error) };
    self.postMessage(reply);
  }
};
