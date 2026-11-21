import shutil

import numpy as np
import pytest
import soundfile as sf

from jca_pipeline.audio import (
    INTERNAL_CHANNELS,
    INTERNAL_SAMPLE_RATE,
    AudioError,
    check_supported,
    conform,
    decode_to_wav,
    read_audio,
    write_flac,
    write_wav,
)

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


@pytest.mark.parametrize("name", ["take.mp3", "take.WAV", "take.flac", "take.m4a"])
def test_supported_formats(tmp_path, name):
    check_supported(tmp_path / name)


@pytest.mark.parametrize("name", ["take.ogg", "take.txt", "take"])
def test_unsupported_formats_are_rejected(tmp_path, name):
    with pytest.raises(AudioError, match="MP3, WAV, FLAC or M4A"):
        check_supported(tmp_path / name)


@needs_ffmpeg
def test_decode_makes_internal_wav_from_mono_22k(tmp_path):
    source = tmp_path / "mono.flac"
    sf.write(source, np.zeros(22050, dtype=np.float32), 22050)
    target = decode_to_wav(source, tmp_path / "source.wav")
    info = sf.info(target)
    assert (info.samplerate, info.channels) == (INTERNAL_SAMPLE_RATE, INTERNAL_CHANNELS)
    assert info.frames == INTERNAL_SAMPLE_RATE


@needs_ffmpeg
def test_decode_of_a_broken_file_raises_with_ffmpeg_output(tmp_path):
    source = tmp_path / "broken.mp3"
    source.write_bytes(b"not audio at all")
    with pytest.raises(AudioError, match="ffmpeg could not decode broken.mp3"):
        decode_to_wav(source, tmp_path / "source.wav")


def test_decode_without_ffmpeg_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(AudioError, match="ffmpeg is not installed"):
        decode_to_wav(tmp_path / "a.wav", tmp_path / "b.wav")


def test_decode_of_a_missing_file_raises(tmp_path):
    with pytest.raises(AudioError, match="not found"):
        decode_to_wav(tmp_path / "missing.wav", tmp_path / "b.wav")


def test_read_audio_is_two_dimensional_float32(tmp_path):
    path = tmp_path / "mono.wav"
    sf.write(path, np.zeros(100), 8000)
    samples, rate = read_audio(path)
    assert (samples.shape, samples.dtype, rate) == ((100, 1), np.float32, 8000)


def test_read_audio_of_a_missing_file_raises(tmp_path):
    with pytest.raises(AudioError, match="missing.wav"):
        read_audio(tmp_path / "missing.wav")


def test_conform_trims_a_long_stem():
    stem = np.ones((10, 2), dtype=np.float32)
    assert conform(stem, 44100, frames=8, sample_rate=44100).shape == (8, 2)


def test_conform_pads_a_short_stem_with_silence():
    stem = np.ones((6, 2), dtype=np.float32)
    padded = conform(stem, 44100, frames=8, sample_rate=44100)
    assert padded.shape == (8, 2)
    assert padded[6:].sum() == 0
    assert stem.shape == (6, 2)


def test_conform_rejects_another_sample_rate():
    with pytest.raises(AudioError, match="48000 Hz.*44100 Hz"):
        conform(np.ones((6, 2), dtype=np.float32), 48000, frames=6, sample_rate=44100)


def test_write_flac_clips_and_keeps_the_frame_count(tmp_path):
    samples = np.array([[2.0, -2.0], [0.5, -0.5]], dtype=np.float32)
    path = write_flac(tmp_path / "stem.flac", samples, 44100)
    back, rate = read_audio(path)
    assert rate == 44100
    np.testing.assert_allclose(back, [[1.0, -1.0], [0.5, -0.5]], atol=1e-4)
    assert sf.info(path).subtype == "PCM_24"


def test_write_wav_keeps_float_values(tmp_path):
    samples = np.array([[0.25, -0.25]], dtype=np.float32)
    back, _ = read_audio(write_wav(tmp_path / "mix.wav", samples, 44100))
    np.testing.assert_array_equal(back, samples)
