def test_voices(client_app):
    r = client_app.get("/api/tts/voices")
    assert r.status_code == 200
    body = r.json()
    assert "voices" in body
    assert "en-US-AndrewNeural" in body["voices"]


def test_with_timing_validates_empty_text(client_app):
    r = client_app.post("/api/tts/with-timing", json={"text": ""})
    assert r.status_code == 422
