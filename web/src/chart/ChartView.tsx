import { useCallback, useEffect, useMemo, useState } from "react";
import type { ApiClient } from "../api/client";
import { exportUrl } from "../api/client";
import type { ChordParts, ChordView, EvidenceSource, GridView, Track } from "../api/types";
import type { LoopRange } from "../audio/engine";
import { BarCell } from "./BarCell";
import { ChordEditor } from "./ChordEditor";
import { GridControls } from "./GridControls";
import type { Selection } from "./model";
import { barsOf, beatIndexAt, editsFor, loopRangeOf, rowsOf, select, selectRange, selectedIndices } from "./model";

export interface PlaybackControl {
  position(): number;
  seek(seconds: number): void;
  setLoop(range: LoopRange | null): void;
}

interface Props {
  readonly trackId: string;
  readonly client: ApiClient;
  readonly playback: PlaybackControl | null;
  readonly onRequeued: (track: Track) => void;
}

const SOURCES: readonly { readonly id: EvidenceSource; readonly label: string }[] = [
  { id: "mix", label: "Mix without drums" },
  { id: "piano", label: "Piano stem" },
  { id: "bass", label: "Bass stem" },
];

export function ChartView({ trackId, client, playback, onRequeued }: Props) {
  const [view, setView] = useState<ChordView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [saving, setSaving] = useState(false);
  const [source, setSource] = useState<EvidenceSource>("mix");
  const [profiles, setProfiles] = useState<readonly (readonly number[])[] | null>(null);
  const [playingIndex, setPlayingIndex] = useState(-1);

  useEffect(() => {
    let cancelled = false;
    client.chords(trackId).then(
      (loaded) => !cancelled && setView(loaded),
      (failure: unknown) => !cancelled && setError(messageOf(failure, "The chart could not be loaded.")),
    );
    return () => {
      cancelled = true;
    };
  }, [client, trackId]);

  useEffect(() => {
    let cancelled = false;
    setProfiles(null);
    client.evidence(trackId, source).then(
      (loaded) => !cancelled && setProfiles(loaded.profiles),
      (failure: unknown) => !cancelled && setError(messageOf(failure, "The evidence could not be loaded.")),
    );
    return () => {
      cancelled = true;
    };
  }, [client, trackId, source]);

  useEffect(() => {
    if (playback === null || view === null) {
      return;
    }
    let frame = 0;
    const tick = () => {
      const index = beatIndexAt(view.beats, playback.position());
      setPlayingIndex((current) => (current === index ? current : index));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playback, view]);

  const rows = useMemo(() => (view === null ? [] : rowsOf(barsOf(view.beats))), [view]);
  const selectedSet = useMemo(() => new Set(selectedIndices(selection)), [selection]);
  const selectedBeats = useMemo(
    () => (view === null ? [] : selectedIndices(selection).map((index) => view.beats[index]).filter((beat) => beat !== undefined)),
    [view, selection],
  );

  const save = useCallback(
    async (parts: ChordParts | null) => {
      if (view === null) {
        return;
      }
      setSaving(true);
      setError(null);
      try {
        setView(await client.saveEdits(trackId, editsFor(view, selection, parts)));
      } catch (failure) {
        setError(messageOf(failure, "The edit could not be saved."));
      } finally {
        setSaving(false);
      }
    },
    [client, trackId, view, selection],
  );

  const applyGrid = useCallback(
    async (grid: GridView) => {
      setError(null);
      try {
        onRequeued(await client.setGrid(trackId, grid));
      } catch (failure) {
        setError(messageOf(failure, "The grid could not be changed."));
      }
    },
    [client, trackId, onRequeued],
  );

  if (view === null) {
    return error !== null ? (
      <p role="alert" className="error">
        {error}
      </p>
    ) : (
      <p className="hint">Loading the chart…</p>
    );
  }
  const firstSelected = selectedBeats[0];
  return (
    <section className="panel chart-view" aria-label="Chord chart">
      <header className="chart-header">
        <h2>Chord chart</h2>
        <nav className="exports" aria-label="Export">
          <a href={exportUrl(trackId, "text")} download>
            Chart (text)
          </a>
          <a href={exportUrl(trackId, "json")} download>
            Analysis (JSON)
          </a>
          <a href={exportUrl(trackId, "stems")} download>
            Stems (ZIP)
          </a>
        </nav>
      </header>
      <div className="chart-toolbar">
        <GridControls grid={view.grid} busy={saving} position={() => playback?.position() ?? 0} onApply={(grid) => void applyGrid(grid)} />
        <label className="field inline">
          Evidence
          <select value={source} onChange={(event) => setSource(event.target.value as EvidenceSource)}>
            {SOURCES.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="legend hint">
        Click a chord to select it, shift-click to extend; click a bass note below it to select one beat. <span className="chord agree-A">A</span> same chord ·{" "}
        <span className="chord agree-B">B</span> other extensions · <span className="chord agree-C">C</span> other class ·{" "}
        <span className="chord agree-D">D</span> other root. Agreement is not proof: both models can be wrong.
      </p>
      {view.unplaced_edits > 0 ? (
        <p className="warning">
          {view.unplaced_edits} earlier {view.unplaced_edits === 1 ? "edit does" : "edits do"} not fall on a beat of the new grid.
          They are kept and come back if the grid is changed back.
        </p>
      ) : null}
      {error !== null ? (
        <p role="alert" className="error">
          {error}
        </p>
      ) : null}
      {firstSelected !== undefined ? (
        <ChordEditor
          beats={selectedBeats}
          saving={saving}
          onSave={(parts) => void save(parts)}
          onLoop={() => playback?.setLoop(loopRangeOf(view, selection))}
          onSetDownbeat={() =>
            void applyGrid({ ...view.grid, beats_per_bar: view.grid.beats_per_bar ?? 4, first_downbeat_index: firstSelected.index })
          }
          onClose={() => setSelection(null)}
        />
      ) : null}
      <div className="bar-rows">
        {rows.map((row) => (
          <div key={row[0]?.number} className="bar-row">
            {row.map((bar) => (
              <BarCell
                key={bar.number}
                bar={bar}
                selected={selectedSet}
                playingIndex={playingIndex}
                profiles={profiles === null ? null : bar.beats.map((beat) => profiles[beat.index] ?? new Array<number>(12).fill(0))}
                onSelect={(index, extend) => setSelection((current) => select(current, index, extend))}
                onSelectRange={(from, to, extend) => setSelection((current) => selectRange(current, from, to, extend))}
                onSeek={(time) => playback?.seek(time)}
              />
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function messageOf(failure: unknown, fallback: string): string {
  return failure instanceof Error ? failure.message : fallback;
}
