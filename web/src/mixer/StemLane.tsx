import { useEffect, useRef } from "react";
import type { PointerEvent } from "react";
import type { Lane } from "../audio/mixState";
import { computePeaks } from "../audio/peaks";
import type { BufferLike } from "../audio/engine";

const WAVE_WIDTH = 1200; // canvas pixels; the canvas is scaled to the lane width by CSS
const WAVE_HEIGHT = 56;

interface Props {
  readonly lane: Lane;
  readonly buffer: BufferLike;
  readonly downloadUrl: string;
  readonly onMute: () => void;
  readonly onSolo: () => void;
  readonly onGain: (gain: number) => void;
  readonly onSeek: (fraction: number) => void;
}

export function StemLane({ lane, buffer, downloadUrl, onMute, onSolo, onGain, onSeek }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const context = canvas.current?.getContext("2d");
    if (context === null || context === undefined) {
      return; // no canvas support (tests)
    }
    const channels = Array.from({ length: buffer.numberOfChannels }, (_, index) => buffer.getChannelData(index));
    const peaks = computePeaks(channels, WAVE_WIDTH);
    const middle = WAVE_HEIGHT / 2;
    context.clearRect(0, 0, WAVE_WIDTH, WAVE_HEIGHT);
    context.fillStyle = getComputedStyle(canvas.current as HTMLCanvasElement).color;
    peaks.forEach((peak, x) => {
      const height = Math.max(1, peak * middle);
      context.fillRect(x, middle - height, 1, height * 2);
    });
  }, [buffer]);

  function seek(event: PointerEvent<HTMLDivElement>) {
    const box = event.currentTarget.getBoundingClientRect();
    if (box.width > 0) {
      onSeek(Math.min(1, Math.max(0, (event.clientX - box.left) / box.width)));
    }
  }

  const audible = !lane.muted;
  return (
    <div role="group" aria-label={lane.name} className={`lane ${lane.kind}${audible ? "" : " muted"}`}>
      <div className="lane-controls">
        <span className="lane-name">{lane.name}</span>
        <button type="button" aria-pressed={lane.solo} className={lane.solo ? "toggle on" : "toggle"} onClick={onSolo}>
          Solo
        </button>
        <button type="button" aria-pressed={lane.muted} className={lane.muted ? "toggle on" : "toggle"} onClick={onMute}>
          Mute
        </button>
        <input
          type="range"
          aria-label="Volume"
          min={0}
          max={1}
          step={0.05}
          value={lane.gain}
          onChange={(event) => onGain(event.target.valueAsNumber)}
        />
        <a href={`${downloadUrl}?download=1`} download>
          Download
        </a>
      </div>
      <div className="wave" data-testid="wave" onPointerDown={seek}>
        <canvas ref={canvas} width={WAVE_WIDTH} height={WAVE_HEIGHT} />
      </div>
    </div>
  );
}
