import { useState } from "react";
import type { DragEvent } from "react";
import type { ApiClient } from "../api/client";
import type { Catalogue, Track } from "../api/types";
import { InstrumentForm } from "./InstrumentForm";
import { ACCEPTED_EXTENSIONS, EMPTY_FORM, formError, isAcceptedFile, toOptions } from "./formState";

const FORMAT_MESSAGE = "Choose an MP3, WAV, FLAC or M4A file.";

interface Props {
  readonly client: ApiClient;
  readonly catalogue: Catalogue;
  readonly onTrack: (track: Track) => void;
}

export function UploadPanel({ client, catalogue, onTrack }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);

  function choose(candidate: File | undefined) {
    if (candidate === undefined) {
      return;
    }
    if (!isAcceptedFile(candidate.name)) {
      setFile(null);
      setError(FORMAT_MESSAGE);
      return;
    }
    setFile(candidate);
    setError(null);
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files[0]);
  }

  async function start() {
    if (file === null) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onTrack(await client.upload(file, toOptions(form, catalogue)));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "The upload failed.");
    } finally {
      setBusy(false);
    }
  }

  const problem = formError(form);
  return (
    <section className="panel upload-panel" aria-label="Upload">
      <h2>Analyse a recording</h2>
      <label
        className={dragging ? "drop-zone dragging" : "drop-zone"}
        data-testid="drop-zone"
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <span>{file === null ? "Drop a recording here, or click to choose one" : file.name}</span>
        <input
          type="file"
          aria-label="Choose a recording (MP3, WAV, FLAC or M4A)"
          accept={ACCEPTED_EXTENSIONS.join(",")}
          onChange={(event) => choose(event.target.files?.[0])}
        />
      </label>
      <InstrumentForm catalogue={catalogue} value={form} onChange={setForm} />
      {error !== null ? (
        <p role="alert" className="error">
          {error}
        </p>
      ) : null}
      {problem !== null && file !== null ? <p className="hint">{problem}</p> : null}
      <button type="button" className="primary" disabled={file === null || problem !== null || busy} onClick={start}>
        {busy ? "Uploading…" : "Start analysis"}
      </button>
    </section>
  );
}
