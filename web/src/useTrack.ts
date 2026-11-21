import { useCallback, useEffect, useState } from "react";
import type { ApiClient } from "./api/client";
import type { Track } from "./api/types";

export const POLL_MILLISECONDS = 2000;

const ACTIVE = new Set(["queued", "running"]);

export interface TrackState {
  readonly track: Track | null;
  readonly error: string | null;
  /** Start polling again, for example after the job was put back in the queue. */
  readonly refresh: () => void;
}

/** Load a track and poll it while its job is queued or running. */
export function useTrack(client: ApiClient, id: string, pollMs: number = POLL_MILLISECONDS): TrackState {
  const [state, setState] = useState<Omit<TrackState, "refresh">>({ track: null, error: null });
  const [version, setVersion] = useState(0);
  const refresh = useCallback(() => setVersion((current) => current + 1), []);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function load() {
      try {
        const track = await client.track(id);
        if (stopped) {
          return;
        }
        setState({ track, error: null });
        if (ACTIVE.has(track.status)) {
          timer = setTimeout(load, pollMs);
        }
      } catch (failure) {
        if (!stopped) {
          setState((current) => ({
            track: current.track,
            error: failure instanceof Error ? failure.message : "The track could not be loaded.",
          }));
          timer = setTimeout(load, pollMs);
        }
      }
    }

    void load();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [client, id, pollMs, version]);

  return { ...state, refresh };
}
