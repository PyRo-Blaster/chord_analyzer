import { useEffect, useState } from "react";
import type { BeatView, ChordParts, Jazz5 } from "../api/types";
import { CLASSES, EXTENSIONS, NOTE_NAMES, formFromParts, partsFromForm, previewTiers, toggleExtension } from "./editorForm";
import { shown } from "./model";

interface Props {
  readonly beats: readonly BeatView[];
  readonly saving: boolean;
  readonly onSave: (parts: ChordParts | null) => void;
  readonly onLoop: () => void;
  readonly onSetDownbeat: () => void;
  readonly onClose: () => void;
}

export function ChordEditor({ beats, saving, onSave, onLoop, onSetDownbeat, onClose }: Props) {
  const first = beats[0];
  const [form, setForm] = useState(() => formFromParts(first === undefined ? emptyParts() : shown(first).parts));

  useEffect(() => {
    if (first !== undefined) {
      setForm(formFromParts(shown(first).parts));
    }
  }, [first]);

  if (first === undefined) {
    return null;
  }
  const last = beats.at(-1) ?? first;
  const range = beats.length === 1 ? `bar ${first.bar}, beat ${first.beat}` : `bar ${first.bar}.${first.beat} to ${last.bar}.${last.beat}`;
  const preview = previewTiers(form);
  return (
    <section className="panel chord-editor" aria-label="Edit chord">
      <header className="editor-header">
        <h3>
          Edit {range} <span className="hint">({beats.length} {beats.length === 1 ? "beat" : "beats"})</span>
        </h3>
        <button type="button" onClick={onClose} aria-label="Close editor">
          ×
        </button>
      </header>
      <div className="suggestions" role="group" aria-label="Suggestions">
        <button type="button" disabled={saving} onClick={() => onSave(partsOfLabel(first, "lv"))}>
          lv-chordia: {first.lv_chordia.symbol}
        </button>
        <button type="button" disabled={saving} onClick={() => onSave(partsOfLabel(first, "btc"))}>
          BTC: {first.btc.symbol}
        </button>
        <button type="button" disabled={saving} onClick={() => onSave(first.draft.parts)}>
          Accept draft ({first.draft.symbol})
        </button>
        <button type="button" disabled={saving || beats.every((beat) => beat.user_edit === null)} onClick={() => onSave(null)}>
          Clear edit
        </button>
      </div>
      <div className="editor-fields">
        <label className="field inline">
          Root
          <select
            value={form.root ?? ""}
            onChange={(event) => setForm({ ...form, root: event.target.value === "" ? null : event.target.value })}
          >
            <option value="">N.C.</option>
            {noteOptions(form.root)}
          </select>
        </label>
        <label className="field inline">
          Class
          <select
            value={form.chordClass ?? ""}
            disabled={form.root === null}
            onChange={(event) =>
              setForm({ ...form, chordClass: event.target.value === "" ? null : (event.target.value as Jazz5) })
            }
          >
            <option value="">none (sus, power chord)</option>
            {CLASSES.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="field inline">
          Bass
          <select
            value={form.bass ?? ""}
            disabled={form.root === null}
            onChange={(event) => setForm({ ...form, bass: event.target.value === "" ? null : event.target.value })}
          >
            <option value="">same as root</option>
            {noteOptions(form.bass)}
          </select>
        </label>
      </div>
      <fieldset className="extensions" disabled={form.root === null}>
        <legend>Extensions</legend>
        {EXTENSIONS.map((name) => (
          <label key={name}>
            <input
              type="checkbox"
              checked={form.extensions.includes(name)}
              onChange={() => setForm(toggleExtension(form, name))}
            />
            {name}
          </label>
        ))}
      </fieldset>
      <p className="preview" aria-label="Preview">
        <span className="tier1">{preview.tier1}</span> <span className="tier2">{preview.tier2}</span>
      </p>
      <div className="editor-actions">
        <button type="button" className="primary" disabled={saving} onClick={() => onSave(partsFromForm(form))}>
          {saving ? "Saving…" : "Save"}
        </button>
        <button type="button" onClick={onLoop}>
          Loop selection
        </button>
        <button type="button" onClick={onSetDownbeat} disabled={beats.length !== 1}>
          Make this beat bar 1
        </button>
      </div>
    </section>
  );
}

function emptyParts(): ChordParts {
  return { root: null, class: null, extensions: [], bass: null };
}

function noteOptions(current: string | null) {
  const names: readonly string[] = current !== null && !NOTE_NAMES.includes(current as never) ? [current, ...NOTE_NAMES] : NOTE_NAMES;
  return names.map((name) => (
    <option key={name} value={name}>
      {name}
    </option>
  ));
}

/** The model's label for the first selected beat, as editable parts (parsed by the server). */
function partsOfLabel(beat: BeatView, model: "lv" | "btc"): ChordParts {
  return (model === "lv" ? beat.lv_chordia : beat.btc).parts;
}
