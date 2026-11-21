import type { LoopRange } from "../audio/engine";

export const SPEEDS = [0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1] as const;

export function formatTime(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

interface Props {
  readonly playing: boolean;
  readonly position: number;
  readonly duration: number;
  readonly speed: number;
  readonly stretching: boolean;
  readonly loop: LoopRange | null;
  readonly loopStart: number | null;
  readonly onPlay: () => void;
  readonly onPause: () => void;
  readonly onSpeed: (speed: number) => void;
  readonly onLoopStart: () => void;
  readonly onLoopEnd: () => void;
  readonly onClearLoop: () => void;
}

export function Transport(props: Props) {
  const { playing, position, duration, speed, stretching, loop, loopStart } = props;
  return (
    <div className="transport" role="toolbar" aria-label="Transport">
      {playing ? (
        <button type="button" className="primary" onClick={props.onPause}>
          Pause
        </button>
      ) : (
        <button type="button" className="primary" onClick={props.onPlay}>
          Play
        </button>
      )}
      <span className="time">
        {formatTime(position)} / {formatTime(duration)}
      </span>
      <label className="field inline">
        Speed
        <select
          value={speed}
          disabled={stretching}
          onChange={(event) => props.onSpeed(Number(event.target.value))}
        >
          {SPEEDS.map((choice) => (
            <option key={choice} value={choice}>
              {Math.round(choice * 100)}%
            </option>
          ))}
        </select>
      </label>
      {stretching ? <span className="hint">Preparing slower audio…</span> : null}
      <button type="button" onClick={props.onLoopStart}>
        Loop start
      </button>
      <button type="button" onClick={props.onLoopEnd} disabled={loopStart === null}>
        Loop end
      </button>
      {loop !== null ? (
        <>
          <span className="loop">
            Loop {formatTime(loop.start)} – {formatTime(loop.end)}
          </span>
          <button type="button" onClick={props.onClearLoop}>
            Clear loop
          </button>
        </>
      ) : null}
    </div>
  );
}
