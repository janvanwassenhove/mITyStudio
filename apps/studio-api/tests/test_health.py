def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "capabilities" in body
    assert set(body["capabilities"]) == {"fluidsynth", "ffmpeg", "voice_clone",
                                         "face_id"}
