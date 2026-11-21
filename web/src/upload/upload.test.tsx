import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ApiClient } from "../api/client";
import { ApiError } from "../api/client";
import type { Catalogue, Track } from "../api/types";
import { InstrumentForm } from "./InstrumentForm";
import { JobProgress } from "./JobProgress";
import { UploadPanel } from "./UploadPanel";
import { EMPTY_FORM } from "./formState";

const CATALOGUE: Catalogue = {
  instruments: ["piano", "double bass", "drums", "tenor sax", "trumpet"],
  horns: ["tenor sax", "trumpet"],
  presets: [
    { id: "piano-trio", label: "Piano trio", instruments: ["piano", "double bass", "drums"], horn_counts: {} },
    { id: "quartet", label: "Quartet with one horn", instruments: ["piano", "double bass", "drums", "tenor sax"], horn_counts: {} },
  ],
};

const STAGES = ["uploaded", "separating", "tracking", "recognising", "decoded"];

function track(overrides: Partial<Track> = {}): Track {
  return {
    id: "t1",
    filename: "take.flac",
    created_at: "2026-11-21T10:00:00.000+00:00",
    status: "running",
    progress: 0.4,
    stages: STAGES.map((name, index) => ({
      name,
      state: index < 2 ? "done" : index === 2 ? "running" : "waiting",
    })),
    warnings: [],
    error: null,
    stems: [],
    ...overrides,
  };
}

function fakeClient(upload: ApiClient["upload"]): ApiClient {
  return {
    catalogue: vi.fn().mockResolvedValue(CATALOGUE),
    tracks: vi.fn().mockResolvedValue([]),
    track: vi.fn(),
    upload,
  };
}

describe("InstrumentForm", () => {
  it("fills the checklist from a preset", async () => {
    const onChange = vi.fn();
    render(<InstrumentForm catalogue={CATALOGUE} value={EMPTY_FORM} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Piano trio" }));
    expect(onChange.mock.calls[0]?.[0].selected).toEqual(["piano", "double bass", "drums"]);
  });

  it("shows a count only for selected horns", () => {
    const value = { ...EMPTY_FORM, selected: ["piano", "trumpet"] };
    render(<InstrumentForm catalogue={CATALOGUE} value={value} onChange={vi.fn()} />);
    expect(screen.getByLabelText("trumpet players")).toBeInTheDocument();
    expect(screen.queryByLabelText("tenor sax players")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("piano players")).not.toBeInTheDocument();
  });

  it("reports a ticked instrument and typed text", async () => {
    const onChange = vi.fn();
    render(<InstrumentForm catalogue={CATALOGUE} value={EMPTY_FORM} onChange={onChange} />);
    await userEvent.click(screen.getByRole("checkbox", { name: "drums" }));
    expect(onChange.mock.calls[0]?.[0].selected).toEqual(["drums"]);
    await userEvent.type(screen.getByLabelText("Other instruments"), "o");
    expect(onChange.mock.lastCall?.[0].otherText).toBe("o");
  });

  it("sets the time signature or leaves it to the tracker", async () => {
    const onChange = vi.fn();
    render(<InstrumentForm catalogue={CATALOGUE} value={EMPTY_FORM} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByLabelText("Beats per bar"), "3");
    expect(onChange.mock.lastCall?.[0].beatsPerBar).toBe(3);
  });
});

describe("UploadPanel", () => {
  it("uploads the chosen file with the form options", async () => {
    const upload = vi.fn().mockResolvedValue(track({ status: "queued" }));
    const onTrack = vi.fn();
    render(<UploadPanel client={fakeClient(upload)} catalogue={CATALOGUE} onTrack={onTrack} />);
    const start = screen.getByRole("button", { name: "Start analysis" });
    expect(start).toBeDisabled();
    await userEvent.upload(screen.getByLabelText(/Choose a recording/), new File(["x"], "take.wav"));
    await userEvent.click(screen.getByRole("button", { name: "Quartet with one horn" }));
    await userEvent.click(start);
    expect(upload).toHaveBeenCalledWith(expect.any(File), {
      instruments: ["piano", "double bass", "drums", "tenor sax"],
      horn_counts: {},
      other: [],
      beats_per_bar: null,
    });
    expect(onTrack).toHaveBeenCalledWith(expect.objectContaining({ id: "t1" }));
  });

  it("rejects a file of another format before uploading", async () => {
    const upload = vi.fn();
    render(<UploadPanel client={fakeClient(upload)} catalogue={CATALOGUE} onTrack={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText(/Choose a recording/), new File(["x"], "take.ogg"), {
      applyAccept: false,
    });
    expect(screen.getByRole("alert")).toHaveTextContent("MP3, WAV, FLAC or M4A");
    expect(screen.getByRole("button", { name: "Start analysis" })).toBeDisabled();
  });

  it("shows the server message when the upload fails", async () => {
    const upload = vi.fn().mockRejectedValue(new ApiError("Unknown instrument 'banjo'", 400));
    render(<UploadPanel client={fakeClient(upload)} catalogue={CATALOGUE} onTrack={vi.fn()} />);
    await userEvent.upload(screen.getByLabelText(/Choose a recording/), new File(["x"], "take.wav"));
    await userEvent.click(screen.getByRole("checkbox", { name: "piano" }));
    await userEvent.click(screen.getByRole("button", { name: "Start analysis" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unknown instrument 'banjo'");
  });

  it("takes a file dropped on the drop zone", async () => {
    render(<UploadPanel client={fakeClient(vi.fn())} catalogue={CATALOGUE} onTrack={vi.fn()} />);
    const zone = screen.getByTestId("drop-zone");
    const file = new File(["x"], "dropped.flac");
    const dataTransfer = { files: [file], types: ["Files"] };
    zone.dispatchEvent(Object.assign(new Event("drop", { bubbles: true }), { dataTransfer }));
    expect(await screen.findByText("dropped.flac")).toBeInTheDocument();
  });
});

describe("JobProgress", () => {
  it("shows each stage with its state and the progress", () => {
    render(<JobProgress track={track()} />);
    const list = screen.getByRole("list", { name: "Stages" });
    const items = within(list).getAllByRole("listitem");
    expect(items.map((item) => item.dataset["state"])).toEqual(["done", "done", "running", "waiting", "waiting"]);
    expect(within(items[1] as HTMLElement).getByText("Separating stems")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
  });

  it("shows warnings and the error of a failed job", () => {
    render(
      <JobProgress
        track={track({
          status: "failed",
          error: "separating failed: out of memory",
          warnings: ["trumpet stays in the residue stem."],
        })}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("separating failed: out of memory");
    expect(screen.getByText("trumpet stays in the residue stem.")).toBeInTheDocument();
  });
});
