import { expect, test } from "@playwright/test";

const RATE = 44100;

/** A short stereo 16-bit WAV: a tone, a bass note and a click every half second. */
function wav(seconds: number): Buffer {
  const frames = RATE * seconds;
  const data = Buffer.alloc(44 + frames * 4);
  data.write("RIFF", 0);
  data.writeUInt32LE(36 + frames * 4, 4);
  data.write("WAVEfmt ", 8);
  data.writeUInt32LE(16, 16);
  data.writeUInt16LE(1, 20);
  data.writeUInt16LE(2, 22);
  data.writeUInt32LE(RATE, 24);
  data.writeUInt32LE(RATE * 4, 28);
  data.writeUInt16LE(4, 32);
  data.writeUInt16LE(16, 34);
  data.write("data", 36);
  data.writeUInt32LE(frames * 4, 40);
  for (let index = 0; index < frames; index += 1) {
    const time = index / RATE;
    const click = index % (RATE / 2) < 400 ? 0.3 : 0;
    const sample = 0.25 * Math.sin(2 * Math.PI * 220 * time) + 0.2 * Math.sin(2 * Math.PI * 55 * time) + click;
    const value = Math.round(Math.max(-1, Math.min(1, sample)) * 32767);
    data.writeInt16LE(value, 44 + index * 4);
    data.writeInt16LE(value, 46 + index * 4);
  }
  return data;
}

test("upload a recording, follow the stages, and play the stems", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel(/Choose a recording/).setInputFiles({
    name: "e2e-take.wav",
    mimeType: "audio/wav",
    buffer: wav(6),
  });
  await page.getByRole("button", { name: "Piano trio" }).click();
  await page.getByRole("button", { name: "Start analysis" }).click();

  await expect(page).toHaveURL(/#\/tracks\/[0-9a-f]{32}$/);
  await expect(page.getByRole("heading", { name: "e2e-take.wav" })).toBeVisible();
  const stages = page.getByRole("list", { name: "Stages" }).getByRole("listitem");
  await expect(stages).toHaveCount(5);
  await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100", { timeout: 30_000 });

  const mixer = page.getByRole("region", { name: "Stem mixer for e2e-take.wav" });
  for (const name of ["drums", "double bass", "piano", "residue"]) {
    await expect(mixer.getByRole("group", { name })).toBeVisible();
  }
  await expect(mixer.getByText("0:00 / 0:06")).toBeVisible();

  const download = mixer.getByRole("group", { name: "double bass" }).getByRole("link", { name: "Download" });
  const reply = await page.request.get((await download.getAttribute("href")) ?? "");
  expect(reply.status()).toBe(200);
  expect(reply.headers()["content-disposition"]).toContain('attachment; filename="e2e-take-double_bass.flac"');

  const mute = mixer.getByRole("group", { name: "drums" }).getByRole("button", { name: "Mute" });
  await mute.click();
  await expect(mute).toHaveAttribute("aria-pressed", "true");

  await mixer.getByRole("button", { name: "Play" }).click();
  await expect(mixer.getByRole("button", { name: "Pause" })).toBeVisible();
  await expect(mixer.getByText(/^0:0[1-5] \/ 0:06$/)).toBeVisible({ timeout: 5_000 });
  await mixer.getByRole("button", { name: "Pause" }).click();

  await mixer.getByLabel("Speed").selectOption("0.75");
  await expect(mixer.getByLabel("Speed")).toHaveValue("0.75");
  await expect(mixer.getByRole("alert")).toHaveCount(0);
});

test("a file in another format is refused before upload", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel(/Choose a recording/).setInputFiles({
    name: "notes.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not audio"),
  });
  await expect(page.getByRole("alert")).toHaveText("Choose an MP3, WAV, FLAC or M4A file.");
  await expect(page.getByRole("button", { name: "Start analysis" })).toBeDisabled();
});
