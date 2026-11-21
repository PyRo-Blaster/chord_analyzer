import { useEffect, useMemo, useState } from "react";
import type { ApiClient } from "./api/client";
import type { Catalogue, Track } from "./api/types";
import type { AudioService } from "./audio/browserAudio";
import { ChartView } from "./chart/ChartView";
import { Mixer } from "./mixer/Mixer";
import { JobProgress } from "./upload/JobProgress";
import { UploadPanel } from "./upload/UploadPanel";
import { useTrack } from "./useTrack";

const TRACK_ROUTE = /^#\/tracks\/([0-9a-f]+)$/;

export function trackIdFromHash(hash: string): string | null {
  return TRACK_ROUTE.exec(hash)?.[1] ?? null;
}

function useHash(): string {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return hash;
}

interface Props {
  readonly client: ApiClient;
  readonly createAudio: () => AudioService;
  readonly pollMs?: number;
}

export function App({ client, createAudio, pollMs }: Props) {
  const trackId = trackIdFromHash(useHash());
  return (
    <div className="app">
      <header className="app-header">
        <a href="#/" className="brand">
          Jazz Chord Analyzer
        </a>
      </header>
      <main>
        {trackId === null ? (
          <Home client={client} />
        ) : (
          <TrackPage key={trackId} client={client} id={trackId} createAudio={createAudio} pollMs={pollMs} />
        )}
      </main>
    </div>
  );
}

function Home({ client }: { readonly client: ApiClient }) {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [recent, setRecent] = useState<readonly Track[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    client.catalogue().then(setCatalogue, (failure: unknown) =>
      setError(failure instanceof Error ? failure.message : "The instrument list could not be loaded."),
    );
    client.tracks().then(setRecent, () => setRecent([]));
  }, [client]);

  if (error !== null) {
    return (
      <p role="alert" className="error">
        {error}
      </p>
    );
  }
  if (catalogue === null) {
    return <p className="hint">Loading…</p>;
  }
  return (
    <>
      <UploadPanel
        client={client}
        catalogue={catalogue}
        onTrack={(track) => {
          window.location.hash = `#/tracks/${track.id}`;
        }}
      />
      {recent.length > 0 ? (
        <section className="panel recent" aria-label="Recent tracks">
          <h2>Recent tracks</h2>
          <ul>
            {recent.map((track) => (
              <li key={track.id}>
                <a href={`#/tracks/${track.id}`}>{track.filename}</a> <span className="hint">{track.status}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

interface TrackPageProps {
  readonly client: ApiClient;
  readonly id: string;
  readonly createAudio: () => AudioService;
  readonly pollMs?: number | undefined;
}

function TrackPage({ client, id, createAudio, pollMs }: TrackPageProps) {
  const { track, error, refresh } = useTrack(client, id, pollMs);
  const audio = useMemo(() => (track !== null && track.stems.length > 0 ? createAudio() : null), [
    createAudio,
    track !== null && track.stems.length > 0,
  ]);

  if (track === null) {
    return error !== null ? (
      <p role="alert" className="error">
        {error}
      </p>
    ) : (
      <p className="hint">Loading…</p>
    );
  }
  return (
    <>
      <JobProgress track={track} />
      {audio !== null ? <Mixer stems={track.stems} trackName={track.filename} audio={audio} /> : null}
      {track.status === "done" ? (
        <ChartView key={track.created_at + track.stages.map((stage) => stage.state).join()} trackId={track.id} client={client} playback={audio?.engine ?? null} onRequeued={refresh} />
      ) : null}
    </>
  );
}
