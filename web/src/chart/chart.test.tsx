import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ApiClient } from "../api/client";
import type { BeatView, ChartEdit, ChordParts, ChordView, EvidenceSource, Track } from "../api/types";
import { ChartView } from "./ChartView";
import type { PlaybackControl } from "./ChartView";
import { formFromParts, partsFromForm, previewTiers, toggleExtension } from "./editorForm";

const C_MAJ7: ChordParts = { root: "C", class: "maj", extensions: ["7"], bass: "C" };
const A_MIN7: ChordParts = { root: "A", class: "min", extensions: ["b7"], bass: "A" };
const D_MIN7: ChordParts = { root: "D", class: "min", extensions: ["b7"], bass: "D" };

function view(symbol: string, parts: ChordParts, tier1: string, tier2: string) {
  return { symbol, parts, tier1, tier2 };
}

function beat(index: number, overrides: Partial<BeatView> = {}): BeatView {
  const second = index >= 4;
  return {
    index,
    bar: Math.floor(index / 4) + 1,
    beat: (index % 4) + 1,
    time: index * 0.5,
    agreement: second ? "D" : "B",
    needs_review: second,
    confidence: second ? 0.2 : 0.7,
    extensions_confidence: 0.3,
    bass_pitch_class: "C",
    lv_chordia: { label: "C:maj7", ...view("Cmaj7", C_MAJ7, "C maj", "7") },
    btc: second
      ? { label: "A:min7", ...view("Am7", A_MIN7, "A min", "b7") }
      : { label: "C:maj", ...view("C", { ...C_MAJ7, extensions: [] }, "C maj", "") },
    draft: view("Cmaj7", C_MAJ7, "C maj", "7"),
    user_edit: null,
    ...overrides,
  };
}

const GRID = { beats_per_bar: null, first_downbeat_index: null, tempo_bpm: null, first_beat_time: null };
const VIEW: ChordView = { beats: Array.from({ length: 8 }, (_, index) => beat(index)), duration: 4, unplaced_edits: 0, grid: GRID };

function fakeClient(overrides: Partial<ApiClient> = {}): ApiClient {
  return {
    catalogue: vi.fn(),
    tracks: vi.fn(),
    track: vi.fn(),
    upload: vi.fn(),
    chords: vi.fn().mockResolvedValue(VIEW),
    saveEdits: vi.fn(async (_id: string, edits: readonly ChartEdit[]) => ({
      ...VIEW,
      beats: VIEW.beats.map((item) =>
        edits.some((edit) => edit.time === item.time && edit.user_edit !== null)
          ? { ...item, user_edit: view("Dm7", D_MIN7, "D min", "b7") }
          : item,
      ),
    })),
    setGrid: vi.fn().mockResolvedValue({ id: "t1", status: "queued" } as Track),
    evidence: vi.fn(async (_id: string, source: EvidenceSource) => ({ source, profiles: VIEW.beats.map(() => [1, ...Array(11).fill(0)]) })),
    ...overrides,
  };
}

function fakePlayback(position = 0): PlaybackControl & { position: ReturnType<typeof vi.fn> } {
  return { position: vi.fn(() => position), seek: vi.fn(), setLoop: vi.fn() };
}

async function renderChart(client = fakeClient(), playback: PlaybackControl | null = fakePlayback(), onRequeued = vi.fn()) {
  render(<ChartView trackId="t1" client={client} playback={playback} onRequeued={onRequeued} />);
  await screen.findByRole("group", { name: "Bar 1" });
  return { client, playback, onRequeued };
}

describe("ChartView", () => {
  it("shows the bars with the chart lane, both model lanes, the bass and the evidence", async () => {
    await renderChart();
    const bar1 = screen.getByRole("group", { name: "Bar 1" });
    expect(within(bar1).getByRole("button", { name: /^Cmaj7, beats 1 2 3 4$/ })).toHaveClass("agree-B");
    expect(within(within(bar1).getByLabelText("lv-chordia")).getByText("Cmaj7")).toBeInTheDocument();
    expect(within(within(bar1).getByLabelText("BTC")).getByText("C")).toBeInTheDocument();
    const bar2 = screen.getByRole("group", { name: "Bar 2" });
    expect(bar2).toHaveClass("review");
    expect(within(bar2).getByRole("button", { name: /Cmaj7/ })).toHaveClass("agree-D");
    expect(await within(bar1).findByLabelText("Evidence: strongest pitch C C C C")).toBeInTheDocument();
  });

  it("selects a chord and saves an edit for each selected beat", async () => {
    const { client } = await renderChart();
    await userEvent.click(within(screen.getByRole("group", { name: "Bar 2" })).getByRole("button", { name: /Cmaj7/ }));
    const editor = screen.getByRole("region", { name: "Edit chord" });
    expect(within(editor).getByText(/Edit bar 2.1 to 2.4/)).toBeInTheDocument();
    await userEvent.selectOptions(within(editor).getByLabelText("Root"), "D");
    await userEvent.selectOptions(within(editor).getByLabelText("Class"), "min");
    await userEvent.click(within(editor).getByLabelText("7"));
    await userEvent.click(within(editor).getByLabelText("b7"));
    expect(within(editor).getByLabelText("Preview")).toHaveTextContent("D min b7");
    await userEvent.click(within(editor).getByRole("button", { name: "Save" }));
    expect(client.saveEdits).toHaveBeenCalledWith("t1", [2, 2.5, 3, 3.5].map((time) => ({ time, user_edit: D_MIN7 })));
    expect(await screen.findByRole("button", { name: /^Dm7, beats 1 2 3 4$/ })).toHaveClass("edited");
  });

  it("selects single beats from the bass row, to split a chord", async () => {
    const { client } = await renderChart();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Beat 3 of bar 2, bass C" }));
    await user.keyboard("{Shift>}");
    await user.click(screen.getByRole("button", { name: "Beat 4 of bar 2, bass C" }));
    await user.keyboard("{/Shift}");
    expect(screen.getByText(/Edit bar 2.3 to 2.4/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "lv-chordia: Cmaj7" }));
    expect(vi.mocked(client.saveEdits).mock.calls[0]?.[1].map((edit) => edit.time)).toEqual([3, 3.5]);
  });

  it("extends the selection with shift and takes a model suggestion in one click", async () => {
    const { client } = await renderChart();
    const user = userEvent.setup();
    const bar2 = screen.getByRole("group", { name: "Bar 2" });
    await user.click(within(screen.getByRole("group", { name: "Bar 1" })).getByRole("button", { name: /Cmaj7/ }));
    await user.keyboard("{Shift>}");
    await user.click(within(bar2).getByRole("button", { name: /Cmaj7/ }));
    await user.keyboard("{/Shift}");
    expect(screen.getByText(/Edit bar 1.1 to 2.4/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "BTC: C" }));
    const sent = vi.mocked(client.saveEdits).mock.calls[0]?.[1] ?? [];
    expect(sent.map((edit) => edit.time)).toEqual([0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5]);
    expect(sent[0]?.user_edit).toEqual({ ...C_MAJ7, extensions: [] });
  });

  it("accepts the draft and clears an edit", async () => {
    const edited = { ...VIEW, beats: VIEW.beats.map((item, index) => (index === 0 ? { ...item, user_edit: view("Dm7", D_MIN7, "D min", "b7") } : item)) };
    const { client } = await renderChart(fakeClient({ chords: vi.fn().mockResolvedValue(edited) }));
    await userEvent.click(screen.getByRole("button", { name: /^Dm7/ }));
    await userEvent.click(screen.getByRole("button", { name: "Clear edit" }));
    expect(client.saveEdits).toHaveBeenLastCalledWith("t1", [{ time: 0, user_edit: null }]);
    await userEvent.click(screen.getByRole("button", { name: /Accept draft/ }));
    expect(client.saveEdits).toHaveBeenLastCalledWith("t1", [{ time: 0, user_edit: C_MAJ7 }]);
  });

  it("shows the server message when an edit fails", async () => {
    await renderChart(fakeClient({ saveEdits: vi.fn().mockRejectedValue(new Error("There is no beat at 2.30 s")) }));
    await userEvent.click(screen.getAllByRole("button", { name: /Cmaj7/ })[0] as HTMLElement);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("There is no beat at 2.30 s");
  });

  it("seeks to a bar and loops the selection", async () => {
    const { playback } = await renderChart();
    await userEvent.click(screen.getByRole("button", { name: /^2/ }));
    expect(playback?.seek).toHaveBeenCalledWith(2);
    await userEvent.click(within(screen.getByRole("group", { name: "Bar 2" })).getByRole("button", { name: /Cmaj7/ }));
    await userEvent.click(screen.getByRole("button", { name: "Loop selection" }));
    expect(playback?.setLoop).toHaveBeenCalledWith({ start: 2, end: 4 });
  });

  it("highlights the beat that is playing", async () => {
    await renderChart(fakeClient(), fakePlayback(2.2));
    await vi.waitFor(() =>
      expect(within(screen.getByRole("group", { name: "Bar 2" })).getByRole("button", { name: /Cmaj7/ })).toHaveClass("playing"),
    );
  });

  it("changes the time signature and moves bar 1", async () => {
    const { client, onRequeued } = await renderChart();
    await userEvent.selectOptions(screen.getByLabelText("Time signature"), "3");
    expect(client.setGrid).toHaveBeenCalledWith("t1", { ...GRID, beats_per_bar: 3, first_downbeat_index: null });
    expect(onRequeued).toHaveBeenCalledWith(expect.objectContaining({ status: "queued" }));
    await userEvent.click(screen.getByRole("button", { name: "Beat 1 of bar 2, bass C" }));
    await userEvent.click(screen.getByRole("button", { name: "Make this beat bar 1" }));
    expect(client.setGrid).toHaveBeenLastCalledWith("t1", { ...GRID, beats_per_bar: 4, first_downbeat_index: 4 });
  });

  it("sets the grid from tapped beats", async () => {
    const playback = fakePlayback();
    const { client } = await renderChart(fakeClient(), playback);
    const tap = screen.getByRole("button", { name: "Tap tempo" });
    for (const time of [10.3, 10.9, 11.5, 12.1]) {
      playback.position.mockReturnValue(time);
      await userEvent.click(tap);
    }
    expect(screen.getByText("100 BPM")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Use tapped tempo" }));
    expect(client.setGrid).toHaveBeenCalledWith("t1", { ...GRID, beats_per_bar: 4, tempo_bpm: 100, first_beat_time: 0.1 });
  });

  it("switches the evidence source", async () => {
    const { client } = await renderChart();
    await userEvent.selectOptions(screen.getByLabelText("Evidence"), "bass");
    expect(client.evidence).toHaveBeenLastCalledWith("t1", "bass");
  });

  it("links the three exports", async () => {
    await renderChart();
    const exports = screen.getByRole("navigation", { name: "Export" });
    expect(within(exports).getByRole("link", { name: "Chart (text)" })).toHaveAttribute("href", "/api/tracks/t1/export?format=text");
    expect(within(exports).getByRole("link", { name: "Stems (ZIP)" })).toHaveAttribute("href", "/api/tracks/t1/export?format=stems");
  });

  it("warns about edits that no longer fall on a beat", async () => {
    await renderChart(fakeClient({ chords: vi.fn().mockResolvedValue({ ...VIEW, unplaced_edits: 2 }) }));
    expect(screen.getByText(/2 earlier edits do not fall on a beat/)).toBeInTheDocument();
  });

  it("shows an error when the chart cannot be loaded", async () => {
    render(
      <ChartView
        trackId="t1"
        client={fakeClient({ chords: vi.fn().mockRejectedValue(new Error("The chart is not ready yet")) })}
        playback={null}
        onRequeued={vi.fn()}
      />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("The chart is not ready yet");
  });
});

describe("editor form", () => {
  it("round-trips parts and treats a bass equal to the root as no slash", () => {
    const form = formFromParts(D_MIN7);
    expect(form.bass).toBeNull();
    expect(partsFromForm(form)).toEqual(D_MIN7);
  });

  it("keeps extensions in the server order and makes N.C. empty", () => {
    const form = toggleExtension(toggleExtension(formFromParts({ ...D_MIN7, extensions: [] }), "9"), "b7");
    expect(partsFromForm(form).extensions).toEqual(["b7", "9"]);
    expect(partsFromForm({ ...form, root: null })).toEqual({ root: null, class: null, extensions: [], bass: null });
    expect(previewTiers({ ...form, bass: "C" })).toEqual({ tier1: "D min", tier2: "b7, 9, bass C" });
    expect(previewTiers({ ...form, root: null })).toEqual({ tier1: "N.C.", tier2: "" });
  });
});
