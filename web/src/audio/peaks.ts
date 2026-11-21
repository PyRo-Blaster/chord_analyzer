/** The loudest absolute sample in each of `buckets` equal slices, across all channels. */
export function computePeaks(channels: readonly Float32Array[], buckets: number): Float32Array {
  const peaks = new Float32Array(buckets);
  const length = channels[0]?.length ?? 0;
  if (length === 0) {
    return peaks;
  }
  for (let bucket = 0; bucket < buckets; bucket += 1) {
    const start = Math.floor((bucket * length) / buckets);
    const end = Math.max(start + 1, Math.floor(((bucket + 1) * length) / buckets));
    let peak = 0;
    for (const channel of channels) {
      for (let index = start; index < Math.min(end, length); index += 1) {
        peak = Math.max(peak, Math.abs(channel[index] ?? 0));
      }
    }
    peaks[bucket] = peak;
  }
  return peaks;
}
