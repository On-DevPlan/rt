import os
import tempfile

import pytest

from rt_backend.tts.cache import TTSCache


@pytest.fixture
def cache():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    c = TTSCache(path)
    yield c
    c.close()
    os.unlink(path)


def test_get_missing_returns_none(cache):
    assert cache.get("missing-key") is None


def test_set_then_get(cache):
    cache.set("k1", "audiodata", "voice-x", "hello", '[{"text":"hi"}]')
    result = cache.get("k1")
    assert result is not None
    audio_b64, words_json = result
    assert audio_b64 == "audiodata"
    assert words_json == '[{"text":"hi"}]'


def test_set_overwrites(cache):
    cache.set("k1", "v1", "voice", "text", None)
    cache.set("k1", "v2", "voice", "text", None)
    audio, _ = cache.get("k1")
    assert audio == "v2"
