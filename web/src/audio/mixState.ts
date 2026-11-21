import type { StemView } from "../api/types";

export interface Lane {
  readonly name: string;
  readonly kind: StemView["kind"];
  readonly gain: number;
  readonly muted: boolean;
  readonly solo: boolean;
}

export function defaultLanes(stems: readonly Pick<StemView, "name" | "kind">[]): readonly Lane[] {
  return stems.map((stem) => ({ name: stem.name, kind: stem.kind, gain: 1, muted: false, solo: false }));
}

/** The gain each lane plays at. Mute wins over solo; with any solo, only soloed lanes play. */
export function effectiveGains(lanes: readonly Lane[]): Readonly<Record<string, number>> {
  const anySolo = lanes.some((lane) => lane.solo);
  return Object.fromEntries(
    lanes.map((lane) => [lane.name, !lane.muted && (!anySolo || lane.solo) ? lane.gain : 0]),
  );
}

export function toggleMute(lanes: readonly Lane[], name: string): readonly Lane[] {
  return update(lanes, name, (lane) => ({ ...lane, muted: !lane.muted }));
}

export function toggleSolo(lanes: readonly Lane[], name: string): readonly Lane[] {
  return update(lanes, name, (lane) => ({ ...lane, solo: !lane.solo }));
}

export function setGain(lanes: readonly Lane[], name: string, gain: number): readonly Lane[] {
  return update(lanes, name, (lane) => ({ ...lane, gain: Math.min(1, Math.max(0, gain)) }));
}

function update(lanes: readonly Lane[], name: string, change: (lane: Lane) => Lane): readonly Lane[] {
  return lanes.map((lane) => (lane.name === name ? change(lane) : lane));
}
