import type { StageState, Track } from "../api/types";

const STAGE_LABELS: Readonly<Record<string, string>> = {
  uploaded: "Decoding the upload",
  separating: "Separating stems",
  tracking: "Tracking beats and bars",
  recognising: "Recognising chords (two models)",
  decoded: "Drafting the chart",
};

const STATE_LABELS: Readonly<Record<StageState, string>> = {
  waiting: "waiting",
  running: "running",
  done: "done",
  failed: "failed",
};

export function JobProgress({ track }: { readonly track: Track }) {
  const percent = Math.round(track.progress * 100);
  return (
    <section className="panel job-progress" aria-label="Analysis progress">
      <h2>{track.filename}</h2>
      <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>
      <ol className="stages" aria-label="Stages">
        {track.stages.map((stage) => (
          <li key={stage.name} className={`stage ${stage.state}`} data-state={stage.state}>
            <span className="stage-name">{STAGE_LABELS[stage.name] ?? stage.name}</span>
            <span className="stage-state">{STATE_LABELS[stage.state]}</span>
          </li>
        ))}
      </ol>
      {track.error !== null ? (
        <p role="alert" className="error">
          {track.error}
        </p>
      ) : null}
      {track.warnings.length > 0 ? (
        <ul className="warnings" aria-label="Warnings">
          {track.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
