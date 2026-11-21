/**
 * WSOLA time-stretch: slower playback without a change of pitch.
 *
 * The search for good frame positions runs once, on the mix. The same positions are then
 * used for every stem, so the stretched stems stay sample-aligned and still add up to the
 * stretched mix (overlap-add is linear).
 */

export const WSOLA = {
  frame: 2048, // about 46 ms at 44.1 kHz
  tolerance: 512, // how far a frame may move from its nominal position
  decimation: 8, // the coarse search runs on the mix downsampled by this factor
  minSpeed: 0.25,
  maxSpeed: 1,
} as const;

const HOP = WSOLA.frame / 2;
const WINDOW = hann(WSOLA.frame);

/** Input start position of each output frame, chosen on `mix`. */
export function computePositions(mix: Float32Array, speed: number): Int32Array {
  if (!(speed >= WSOLA.minSpeed && speed <= WSOLA.maxSpeed)) {
    throw new RangeError(`speed must be from ${WSOLA.minSpeed} to ${WSOLA.maxSpeed}, got ${speed}`);
  }
  const lastStart = mix.length - WSOLA.frame;
  if (lastStart <= 0) {
    return new Int32Array(0);
  }
  const analysisHop = HOP * speed;
  const count = Math.floor(lastStart / analysisHop) + 1;
  const positions = new Int32Array(count);
  const coarse = downsample(mix, WSOLA.decimation);
  let previous = 0;
  for (let frame = 1; frame < count; frame += 1) {
    const nominal = Math.round(frame * analysisHop);
    const target = previous + HOP; // where the previous frame would naturally continue
    positions[frame] = bestPosition(mix, coarse, nominal, target, lastStart);
    previous = positions[frame] ?? nominal;
  }
  return positions;
}

/** Overlap-add Hann-windowed frames of `channel` taken at `positions`. */
export function renderWithPositions(channel: Float32Array, positions: Int32Array): Float32Array {
  const output = new Float32Array(positions.length * HOP + HOP);
  positions.forEach((start, frame) => {
    const offset = frame * HOP;
    for (let index = 0; index < WSOLA.frame; index += 1) {
      output[offset + index] = (output[offset + index] ?? 0) + (channel[start + index] ?? 0) * (WINDOW[index] ?? 0);
    }
  });
  return output;
}

/** Stretch every stem (an array of channels) with positions found on their sum. */
export function stretchStems(stems: readonly (readonly Float32Array[])[], speed: number): Float32Array[][] {
  const length = stems[0]?.[0]?.length ?? 0;
  const mix = new Float32Array(length);
  for (const stem of stems) {
    for (const channel of stem) {
      for (let index = 0; index < length; index += 1) {
        mix[index] = (mix[index] ?? 0) + (channel[index] ?? 0);
      }
    }
  }
  const positions = computePositions(mix, speed);
  return stems.map((stem) => stem.map((channel) => renderWithPositions(channel, positions)));
}

function bestPosition(
  mix: Float32Array,
  coarse: Float32Array,
  nominal: number,
  target: number,
  lastStart: number,
): number {
  const low = Math.max(0, nominal - WSOLA.tolerance);
  const high = Math.min(lastStart, nominal + WSOLA.tolerance);
  const step = WSOLA.decimation;
  let coarseBest = Math.min(Math.max(nominal, low), high);
  let coarseScore = -Infinity;
  for (let candidate = low; candidate <= high; candidate += step) {
    const score = similarity(coarse, Math.floor(target / step), Math.floor(candidate / step), HOP / step);
    if (score > coarseScore) {
      coarseScore = score;
      coarseBest = candidate;
    }
  }
  // The natural continuation goes first: it scores the most possible (an exact match), so
  // at full speed every frame stays where it is and the audio passes through unchanged.
  const candidates = [target, ...range(Math.max(low, coarseBest - step), Math.min(high, coarseBest + step))];
  let best = coarseBest;
  let bestScore = -Infinity;
  for (const candidate of candidates) {
    if (candidate < low || candidate > high) {
      continue;
    }
    const score = similarity(mix, target, candidate, HOP);
    if (score > bestScore) {
      bestScore = score;
      best = candidate;
    }
  }
  return best;
}

/** Normalised cross-correlation of the segment at `b` with the segment at `a`. */
function similarity(signal: Float32Array, a: number, b: number, length: number): number {
  let product = 0;
  let energy = 0;
  for (let index = 0; index < length; index += 1) {
    const candidate = signal[b + index] ?? 0;
    product += (signal[a + index] ?? 0) * candidate;
    energy += candidate * candidate;
  }
  return product / Math.sqrt(energy + 1e-12);
}

function range(from: number, to: number): number[] {
  return Array.from({ length: Math.max(0, to - from + 1) }, (_, index) => from + index);
}

function downsample(signal: Float32Array, factor: number): Float32Array {
  const result = new Float32Array(Math.ceil(signal.length / factor));
  for (let index = 0; index < result.length; index += 1) {
    let sum = 0;
    for (let offset = 0; offset < factor; offset += 1) {
      sum += signal[index * factor + offset] ?? 0;
    }
    result[index] = sum / factor;
  }
  return result;
}

function hann(length: number): Float32Array {
  // Periodic Hann: at a hop of half the frame, the windows add up to exactly 1.
  return Float32Array.from({ length }, (_, index) => 0.5 - 0.5 * Math.cos((2 * Math.PI * index) / length));
}
