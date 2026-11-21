import hashlib
import re

import pytest

from jca_core.cache.key import file_sha256, stem_cache_key
from jca_core.separation.plan import Instrument

AUDIO = "a" * 64
SEPARATOR = "bs-roformer-sw"
TRIO = [Instrument.PIANO, Instrument.DOUBLE_BASS, Instrument.DRUMS]


def test_key_is_a_stable_sha256():
    key = stem_cache_key(AUDIO, SEPARATOR, TRIO)
    assert re.fullmatch(r"[0-9a-f]{64}", key)
    assert key == stem_cache_key(AUDIO, SEPARATOR, TRIO)


def test_key_does_not_depend_on_the_order_of_the_instruments():
    assert stem_cache_key(AUDIO, SEPARATOR, TRIO) == stem_cache_key(AUDIO, SEPARATOR, TRIO[::-1])


def test_key_changes_with_each_input():
    base = stem_cache_key(AUDIO, SEPARATOR, TRIO)
    changed = {
        stem_cache_key("b" * 64, SEPARATOR, TRIO),
        stem_cache_key(AUDIO, "htdemucs_6s", TRIO),
        stem_cache_key(AUDIO, SEPARATOR, [*TRIO, Instrument.ALTO_SAX]),
        stem_cache_key(AUDIO, SEPARATOR, TRIO, other=["organ"]),
        stem_cache_key(
            AUDIO, SEPARATOR, [*TRIO, Instrument.TRUMPET], horn_counts={Instrument.TRUMPET: 2}
        ),
    }
    assert base not in changed
    assert len(changed) == 5


def test_free_text_instruments_are_normalised():
    first = stem_cache_key(AUDIO, SEPARATOR, TRIO, other=["  Organ "])
    second = stem_cache_key(AUDIO, SEPARATOR, TRIO, other=["organ", "ORGAN"])
    assert first == second


def test_a_count_of_one_is_the_same_as_no_count():
    with_trumpet = [*TRIO, Instrument.TRUMPET]
    first = stem_cache_key(AUDIO, SEPARATOR, with_trumpet, horn_counts={Instrument.TRUMPET: 1})
    assert first == stem_cache_key(AUDIO, SEPARATOR, with_trumpet)


@pytest.mark.parametrize("audio", ["", "abc", "A" * 64, "g" * 64])
def test_audio_hash_must_be_a_sha256(audio):
    with pytest.raises(ValueError, match="64 lowercase hex"):
        stem_cache_key(audio, SEPARATOR, TRIO)


def test_separator_must_be_named():
    with pytest.raises(ValueError, match="separator"):
        stem_cache_key(AUDIO, "", TRIO)


def test_file_sha256_hashes_the_file_content(tmp_path):
    path = tmp_path / "take.flac"
    path.write_bytes(b"not really audio")
    assert file_sha256(path) == hashlib.sha256(b"not really audio").hexdigest()


def test_file_sha256_of_a_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        file_sha256(tmp_path / "missing.flac")
