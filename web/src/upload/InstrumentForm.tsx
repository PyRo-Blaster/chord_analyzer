import type { Catalogue } from "../api/types";
import type { FormState } from "./formState";
import { MAX_HORN_COUNT, MIN_HORN_COUNT, applyPreset, setHornCount, toggleInstrument } from "./formState";

const BEATS_PER_BAR_CHOICES = [2, 3, 4, 5, 6, 7, 9, 12] as const;

interface Props {
  readonly catalogue: Catalogue;
  readonly value: FormState;
  readonly onChange: (next: FormState) => void;
}

export function InstrumentForm({ catalogue, value, onChange }: Props) {
  return (
    <fieldset className="instrument-form">
      <legend>Instruments in the track</legend>
      <div className="presets" role="group" aria-label="Presets">
        {catalogue.presets.map((preset) => (
          <button
            key={preset.id}
            type="button"
            className={preset.id === value.presetId ? "preset active" : "preset"}
            aria-pressed={preset.id === value.presetId}
            onClick={() => onChange(applyPreset(value, catalogue, preset.id))}
          >
            {preset.label}
          </button>
        ))}
      </div>
      <ul className="checklist">
        {catalogue.instruments.map((name) => {
          const selected = value.selected.includes(name);
          const isHorn = catalogue.horns.includes(name);
          return (
            <li key={name}>
              <label>
                <input type="checkbox" checked={selected} onChange={() => onChange(toggleInstrument(value, name))} />
                {name}
              </label>
              {selected && isHorn ? (
                <input
                  type="number"
                  className="count"
                  aria-label={`${name} players`}
                  min={MIN_HORN_COUNT}
                  max={MAX_HORN_COUNT}
                  value={value.hornCounts[name] ?? MIN_HORN_COUNT}
                  onChange={(event) => onChange(setHornCount(value, name, event.target.valueAsNumber))}
                />
              ) : null}
            </li>
          );
        })}
      </ul>
      <label className="field">
        Other instruments
        <input
          type="text"
          placeholder="organ, harp"
          value={value.otherText}
          onChange={(event) => onChange({ ...value, otherText: event.target.value })}
        />
      </label>
      <label className="field">
        Beats per bar
        <select
          value={value.beatsPerBar ?? ""}
          onChange={(event) =>
            onChange({ ...value, beatsPerBar: event.target.value === "" ? null : Number(event.target.value) })
          }
        >
          <option value="">Let the beat tracker decide</option>
          {BEATS_PER_BAR_CHOICES.map((count) => (
            <option key={count} value={count}>
              {count}
            </option>
          ))}
        </select>
      </label>
    </fieldset>
  );
}
