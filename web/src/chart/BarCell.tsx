import { useEffect, useRef } from "react";
import type { MouseEvent } from "react";
import type { BeatView } from "../api/types";
import type { Bar } from "./model";
import { segmentsOf, shown } from "./model";

const EVIDENCE_ROWS = 12;
const PITCH_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];

interface Props {
  readonly bar: Bar;
  readonly selected: ReadonlySet<number>;
  readonly playingIndex: number;
  readonly profiles: readonly (readonly number[])[] | null;
  readonly onSelect: (index: number, extend: boolean) => void;
  readonly onSeek: (time: number) => void;
}

export function BarCell({ bar, selected, playingIndex, profiles, onSelect, onSeek }: Props) {
  const columns = { gridTemplateColumns: `repeat(${bar.beats.length}, 1fr)` };
  const first = bar.beats[0];
  const review = bar.beats.some((beat) => beat.needs_review);
  return (
    <div className={review ? "bar review" : "bar"} role="group" aria-label={`Bar ${bar.number}`}>
      <button type="button" className="bar-number" onClick={() => first !== undefined && onSeek(first.time)}>
        {bar.number === 0 ? "pickup" : bar.number}
        {review ? <span className="review-mark" title="Marked for review: the models disagree or the bass does not fit"> ?</span> : null}
      </button>
      <div className="lane chart-lane" style={columns}>
        {segmentsOf(bar.beats, (beat) => `${shown(beat).symbol}|${beat.agreement}|${beat.user_edit !== null}`).map(
          (segment) => {
            const beat = segment.beats[0] as BeatView;
            const label = shown(beat);
            const classes = [
              "chord",
              `agree-${beat.agreement}`,
              beat.user_edit !== null ? "edited" : "",
              segment.beats.some((item) => selected.has(item.index)) ? "selected" : "",
              segment.beats.some((item) => item.index === playingIndex) ? "playing" : "",
            ];
            return (
              <button
                key={beat.index}
                type="button"
                className={classes.filter(Boolean).join(" ")}
                style={{ gridColumn: `span ${segment.beats.length}` }}
                aria-label={`${label.symbol}, beats ${segment.beats.map((item) => item.beat).join(" ")}`}
                title={`Agreement ${beat.agreement} · confidence ${Math.round(beat.confidence * 100)}%`}
                onClick={(event: MouseEvent) => onSelect(beat.index, event.shiftKey)}
                onDoubleClick={() => onSelect(segment.beats.at(-1)?.index ?? beat.index, true)}
              >
                <span className="tier1">{label.tier1}</span>
                <span className="tier2" title={`confidence ${Math.round(beat.extensions_confidence * 100)}%`}>
                  {label.tier2}
                </span>
              </button>
            );
          },
        )}
      </div>
      <ModelLane name="lv-chordia" beats={bar.beats} columns={columns} pick={(beat) => beat.lv_chordia.symbol} />
      <ModelLane name="BTC" beats={bar.beats} columns={columns} pick={(beat) => beat.btc.symbol} />
      <div className="lane bass-lane" style={columns} aria-label="Bass">
        {bar.beats.map((beat) => (
          <span key={beat.index}>{beat.bass_pitch_class ?? "·"}</span>
        ))}
      </div>
      <EvidenceStrip profiles={profiles} />
    </div>
  );
}

function ModelLane({
  name,
  beats,
  columns,
  pick,
}: {
  readonly name: string;
  readonly beats: readonly BeatView[];
  readonly columns: { gridTemplateColumns: string };
  readonly pick: (beat: BeatView) => string;
}) {
  return (
    <div className="lane model-lane" style={columns} aria-label={name}>
      {segmentsOf(beats, pick).map((segment) => (
        <span key={segment.beats[0]?.index} style={{ gridColumn: `span ${segment.beats.length}` }}>
          {segment.key}
        </span>
      ))}
    </div>
  );
}

function EvidenceStrip({ profiles }: { readonly profiles: readonly (readonly number[])[] | null }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const context = canvas.current?.getContext("2d");
    if (context === null || context === undefined || profiles === null) {
      return;
    }
    context.clearRect(0, 0, profiles.length, EVIDENCE_ROWS);
    profiles.forEach((profile, column) => {
      profile.forEach((value, pitch) => {
        context.fillStyle = `rgba(47, 93, 138, ${value})`;
        context.fillRect(column, EVIDENCE_ROWS - 1 - pitch, 1, 1);
      });
    });
  }, [profiles]);
  if (profiles === null) {
    return <div className="evidence empty" aria-label="Evidence" />;
  }
  const strongest = profiles.map((profile) => PITCH_NAMES[profile.indexOf(Math.max(...profile))] ?? "");
  return (
    <canvas
      ref={canvas}
      className="evidence"
      width={Math.max(1, profiles.length)}
      height={EVIDENCE_ROWS}
      aria-label={`Evidence: strongest pitch ${strongest.join(" ")}`}
    />
  );
}
