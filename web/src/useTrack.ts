import { useEffect, useState } from "react";
import type { ApiClient } from "./api/client";
import type { Track } from "./api/types";

export const POLL_MILLISECONDS = 2000;

const ACTIVE = new Set(["queued", "running"]);

export interface TrackState {
  readonly track: Track | null;
  readonly error: string | null;
}

/** Load a track and poll it while its job is queued or running. */
export function useTrack(client: ApiClient, id: string, pollMs: number = POLL_MILLISECONDS): TrackState {
  const [state, setState] = useState<TrackState>({ track: null, error: null });

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

    setState({ track: null, error: null });
    void load();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [client, id, pollMs]);

  return state;
}
