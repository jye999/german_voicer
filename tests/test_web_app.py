from __future__ import annotations

import io
from pathlib import Path

from voice_german_cloner.web import create_app


def test_home_page_has_recorder_and_text_form(tmp_path: Path) -> None:
    app = create_app(output_dir=tmp_path / "outputs", sample_dir=tmp_path / "samples")

    response = app.test_client().get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Record my voice" in html
    assert "English text" in html
    assert "Generate German Voice" in html


def test_generate_accepts_recorded_voice_and_returns_audio_url(tmp_path: Path) -> None:
    calls: list[tuple[str, Path, Path]] = []

    def fake_translate(text: str) -> str:
        assert text == "Good morning"
        return "Guten Morgen"

    def fake_synthesize(german_text: str, speaker_wav: Path, output_path: Path) -> None:
        calls.append((german_text, speaker_wav, output_path))
        output_path.write_bytes(b"fake-wav")

    app = create_app(
        output_dir=tmp_path / "outputs",
        sample_dir=tmp_path / "samples",
        translator=fake_translate,
        synthesizer=fake_synthesize,
    )

    response = app.test_client().post(
        "/generate",
        data={
            "text": "Good morning",
            "voice": (io.BytesIO(b"webm audio bytes"), "recording.webm"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {
        "english": "Good morning",
        "german": "Guten Morgen",
        "audio_url": "/outputs/german_voice_001.wav",
    }
    assert calls and calls[0][0] == "Guten Morgen"
    assert calls[0][1].exists()
    assert calls[0][1].suffix == ".webm"
    assert (tmp_path / "outputs" / "german_voice_001.wav").read_bytes() == b"fake-wav"


def test_generate_requires_text_and_voice(tmp_path: Path) -> None:
    app = create_app(output_dir=tmp_path / "outputs", sample_dir=tmp_path / "samples")

    response = app.test_client().post("/generate", data={}, content_type="multipart/form-data")

    assert response.status_code == 400
    assert "English text is required" in response.get_json()["error"]
