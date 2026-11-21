import { useState } from "react";
import type { GridView } from "../api/types";
import { tapTempo } from "./model";

const BEATS_PER_BAR_CHOICES = [2, 3, 4, 5, 6, 7, 9, 12] as const;

interface Props {
  readonly grid: GridView;
  readonly busy: boolean;
  readonly position: () => number;
  readonly onApply: (grid: GridView) => void;
}

export function GridControls({ grid, busy, position, onApply }: Props) {
  const [taps, setTaps] = useState<readonly number[]>([]);
  const tapped = tapTempo(taps);

  return (
    <div className="grid-controls" role="group" aria-label="Bar grid">
      <label className="field inline">
        Time signature
        <select
          value={grid.beats_per_bar ?? ""}
          disabled={busy}
          onChange={(event) => {
            const value = event.target.value === "" ? null : Number(event.target.value);
            onApply({ ...grid, beats_per_bar: value, first_downbeat_index: value === null ? null : grid.first_downbeat_index });
          }}
        >
          <option value="">From the beat tracker</option>
          {BEATS_PER_BAR_CHOICES.map((count) => (
            <option key={count} value={count}>
              {count} beats a bar
            </option>
          ))}
        </select>
      </label>
      <button type="button" disabled={busy} onClick={() => setTaps([...taps, position()])}>
        Tap tempo
      </button>
      <span className="hint" aria-live="polite">
        {tapped !== null ? `${tapped.tempo_bpm} BPM` : taps.length > 0 ? `${taps.length} taps (4 needed)` : "Play and tap on the beat"}
      </span>
      <button
        type="button"
        disabled={busy || tapped === null}
        onClick={() => {
          if (tapped !== null) {
            onApply({ ...grid, beats_per_bar: grid.beats_per_bar ?? 4, ...tapped });
            setTaps([]);
          }
        }}
      >
        Use tapped tempo
      </button>
      {taps.length > 0 ? (
        <button type="button" onClick={() => setTaps([])}>
          Reset taps
        </button>
      ) : null}
      {grid.tempo_bpm !== null ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => onApply({ ...grid, tempo_bpm: null, first_beat_time: null })}
        >
          Back to the beat tracker
        </button>
      ) : null}
    </div>
  );
}
