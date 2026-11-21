import type { ChordParts, Jazz5 } from "../api/types";

export const NOTE_NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"] as const;
export const CLASSES: readonly Jazz5[] = ["maj", "min", "dom7", "hdim7", "dim"];
// The degree names the server accepts, in its display order (jca_core EXTENSION_NAMES).
export const EXTENSIONS = ["2", "3", "4", "b5", "5", "#5", "6", "bb7", "b7", "7", "b9", "9", "#9", "11", "#11", "b13", "13"] as const;

export interface EditorForm {
  readonly root: string | null;
  readonly chordClass: Jazz5 | null;
  readonly extensions: readonly string[];
  readonly bass: string | null; // null: the bass is the root
}

export function formFromParts(parts: ChordParts): EditorForm {
  return {
    root: parts.root,
    chordClass: parts.class,
    extensions: [...parts.extensions],
    bass: parts.bass !== null && parts.bass !== parts.root ? parts.bass : null,
  };
}

export function partsFromForm(form: EditorForm): ChordParts {
  if (form.root === null) {
    return { root: null, class: null, extensions: [], bass: null };
  }
  const ordered = EXTENSIONS.filter((name) => form.extensions.includes(name));
  return { root: form.root, class: form.chordClass, extensions: ordered, bass: form.bass ?? form.root };
}

export function toggleExtension(form: EditorForm, name: string): EditorForm {
  const has = form.extensions.includes(name);
  return { ...form, extensions: has ? form.extensions.filter((item) => item !== name) : [...form.extensions, name] };
}

/** Preview of the two tiers while editing; the server sends the final text after saving. */
export function previewTiers(form: EditorForm): { readonly tier1: string; readonly tier2: string } {
  if (form.root === null) {
    return { tier1: "N.C.", tier2: "" };
  }
  const tier1 = form.chordClass === null ? form.root : `${form.root} ${form.chordClass}`;
  const ordered = EXTENSIONS.filter((name) => form.extensions.includes(name));
  const bass = form.bass !== null && form.bass !== form.root ? [`bass ${form.bass}`] : [];
  return { tier1, tier2: [...ordered, ...bass].join(", ") };
}
