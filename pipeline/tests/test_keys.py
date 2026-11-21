import re

from jca_pipeline.keys import decoding_key, recognition_key, tracking_key

SHA = "a" * 64


def test_keys_are_sha256_hex():
    assert re.fullmatch(r"[0-9a-f]{64}", tracking_key(SHA, "beat-this", None, None))


def test_tracking_key_changes_with_the_time_signature_only_when_set():
    base = tracking_key(SHA, "beat-this", None, None)
    assert base == tracking_key(SHA, "beat-this", None, None)
    assert base != tracking_key(SHA, "beat-this", 3, 0)
    assert tracking_key(SHA, "beat-this", 4, 0) != tracking_key(SHA, "beat-this", 4, 1)
    assert base != tracking_key("b" * 64, "beat-this", None, None)
    assert base != tracking_key(SHA, "madmom", None, None)


def test_recognition_key_follows_the_stems_and_the_input():
    base = recognition_key("sep1", "no_drums", {"lv": "full"})
    assert base != recognition_key("sep2", "no_drums", {"lv": "full"})
    assert base != recognition_key("sep1", "full_mix", {"lv": "full"})
    assert base != recognition_key("sep1", "no_drums", {"lv": "submission"})


def test_decoding_key_follows_every_input():
    base = decoding_key("sep", "trk", "rec", "lv_chordia", True)
    others = {
        decoding_key("sep2", "trk", "rec", "lv_chordia", True),
        decoding_key("sep", "trk2", "rec", "lv_chordia", True),
        decoding_key("sep", "trk", "rec2", "lv_chordia", True),
        decoding_key("sep", "trk", "rec", "btc", True),
        decoding_key("sep", "trk", "rec", "lv_chordia", False),
    }
    assert base not in others
    assert len(others) == 5
