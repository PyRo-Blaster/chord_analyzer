import { useEffect, useState } from "react";
import type { StemView } from "../api/types";
import type { AudioService } from "../audio/browserAudio";
import type { LoopRange, StemBuffer } from "../audio/engine";
import { defaultLanes, effectiveGains, setGain, toggleMute, toggleSolo } from "../audio/mixState";
import type { Lane } from "../audio/mixState";
import { StemLane } from "./StemLane";
import { Transport } from "./Transport";

interface Props {
  readonly stems: readonly StemView[];
  readonly trackName: string;
  readonly audio: AudioService;
}

export function Mixer({ stems, trackName, audio }: Props) {
  const engine = audio.engine;
  const stemKey = stems.map((stem) => stem.url).join("|");
  const [buffers, setBuffers] = useState<readonly StemBuffer[] | null>(null);
  const [lanes, setLanes] = useState<readonly Lane[]>(() => defaultLanes(stems));
  const [error, setError] = useState<string | null>(null);
  const [position, setPosition] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [stretching, setStretching] = useState(false);
  const [loop, setLoop] = useState<LoopRange | null>(null);
  const [loopStart, setLoopStart] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    audio.load(stems).then(
      (loaded) => {
        if (!cancelled) {
          engine.setStems(loaded);
          setBuffers(loaded);
        }
      },
      (failure: unknown) => {
        if (!cancelled) {
          setError(failure instanceof Error ? failure.message : "The stems could not be loaded.");
        }
      },
    );
    return () => {
      cancelled = true;
    };
    // stemKey stands for the stems: a new list with the same files must not reload them
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audio, engine, stemKey]);

  useEffect(() => () => audio.close(), [audio]);

  useEffect(() => {
    engine.setGains(effectiveGains(lanes));
  }, [engine, lanes, buffers]);

  useEffect(() => {
    engine.onEnded = () => setPlaying(false);
    let frame = 0;
    const tick = () => {
      setPosition(engine.position());
      const engineLoop = engine.loopRange; // a loop can also be set from the chord chart
      setLoop((current) => (current === engineLoop ? current : engineLoop));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      engine.onEnded = null;
    };
  }, [engine]);

  const duration = buffers === null ? 0 : engine.duration;
  const progress = duration > 0 ? Math.min(1, position / duration) : 0;

  async function changeSpeed(next: number) {
    if (buffers === null) {
      return;
    }
    setError(null);
    if (!engine.hasSpeed(next)) {
      setStretching(true);
      try {
        engine.setStretched(next, await audio.stretch(next, buffers));
      } catch (failure) {
        setError(failure instanceof Error ? failure.message : "The slower audio could not be prepared.");
        return;
      } finally {
        setStretching(false);
      }
    }
    engine.setSpeed(next);
    setSpeed(next);
  }

  function seek(seconds: number) {
    engine.seek(seconds);
    setPosition(engine.position());
  }

  function applyLoop(range: LoopRange | null) {
    engine.setLoop(range);
    setLoop(range);
  }

  if (error !== null && buffers === null) {
    return (
      <p role="alert" className="error">
        {error}
      </p>
    );
  }
  if (buffers === null) {
    return <p className="hint">Loading stems…</p>;
  }
  return (
    <section className="panel mixer" aria-label={`Stem mixer for ${trackName}`}>
      <h2>Stems</h2>
      <Transport
        playing={playing}
        position={position}
        duration={duration}
        speed={speed}
        stretching={stretching}
        loop={loop}
        loopStart={loopStart}
        onPlay={() => {
          engine.play();
          setPlaying(engine.playing);
        }}
        onPause={() => {
          engine.pause();
          setPlaying(false);
          setPosition(engine.position());
        }}
        onSpeed={(next) => void changeSpeed(next)}
        onLoopStart={() => setLoopStart(engine.position())}
        onLoopEnd={() => {
          const end = engine.position();
          if (loopStart !== null && end > loopStart) {
            applyLoop({ start: loopStart, end });
          }
        }}
        onClearLoop={() => {
          applyLoop(null);
          setLoopStart(null);
        }}
      />
      {error !== null ? (
        <p role="alert" className="error">
          {error}
        </p>
      ) : null}
      <div className="lanes">
        {lanes.map((lane) => {
          const stem = stems.find((candidate) => candidate.name === lane.name);
          const buffer = buffers.find((candidate) => candidate.name === lane.name)?.buffer;
          if (stem === undefined || buffer === undefined) {
            return null;
          }
          return (
            <StemLane
              key={lane.name}
              lane={lane}
              buffer={buffer}
              downloadUrl={stem.url}
              onMute={() => setLanes((current) => toggleMute(current, lane.name))}
              onSolo={() => setLanes((current) => toggleSolo(current, lane.name))}
              onGain={(gain) => setLanes((current) => setGain(current, lane.name, gain))}
              onSeek={(fraction) => seek(fraction * duration)}
              progress={progress}
            />
          );
        })}
      </div>
    </section>
  );
}
