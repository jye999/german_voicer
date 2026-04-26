from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

from voice_german_cloner.web import create_app


def test_home_page_has_cloning_ui(tmp_path: Path) -> None:
    app = create_app(output_dir=tmp_path / "outputs", sample_dir=tmp_path / "samples")

    response = app.test_client().get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Start recording" in html
    assert ".m4a" in html
    assert "English text" in html
    assert "Generate German voice" in html
    assert "Qwen3-TTS" in html
    assert "Reference transcript" in html
    assert "Whisper" in html
    assert "Saved voices" in html


def test_generate_with_voice_returns_audio_url(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_translate(text: str) -> str:
        assert text == "Good morning"
        return "Guten Morgen"

    def fake_synthesize(
        german_text: str,
        speaker_wav: Path,
        output_path: Path,
        *,
        ref_text: str | None = None,
        auto_transcribe_reference: bool = False,
    ) -> None:
        calls.append(
            {
                "german": german_text,
                "speaker": speaker_wav,
                "out": output_path,
                "ref_text": ref_text,
                "auto": auto_transcribe_reference,
            }
        )
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
    assert calls and calls[0]["german"] == "Guten Morgen"
    assert calls[0]["ref_text"] is None
    assert calls[0]["auto"] is False
    assert Path(calls[0]["speaker"]).exists()
    assert Path(calls[0]["speaker"]).suffix == ".webm"
    assert (tmp_path / "outputs" / "german_voice_001.wav").read_bytes() == b"fake-wav"


def test_generate_passes_ref_text_for_icl(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_translate(text: str) -> str:
        return "Hi"

    def fake_synthesize(
        german_text: str,
        speaker_wav: Path,
        output_path: Path,
        *,
        ref_text: str | None = None,
        auto_transcribe_reference: bool = False,
    ) -> None:
        calls.append({"ref_text": ref_text, "auto": auto_transcribe_reference})
        output_path.write_bytes(b"x")

    app = create_app(
        output_dir=tmp_path / "outputs",
        sample_dir=tmp_path / "samples",
        translator=fake_translate,
        synthesizer=fake_synthesize,
    )

    response = app.test_client().post(
        "/generate",
        data={
            "text": "Hi",
            "voice": (io.BytesIO(b"a"), "r.webm"),
            "ref_text": "  Exact words I said.  ",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert calls[0]["ref_text"] == "Exact words I said."
    assert calls[0]["auto"] is False


def test_generate_auto_transcribe_flag(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_translate(text: str) -> str:
        return "Hi"

    def fake_synthesize(
        german_text: str,
        speaker_wav: Path,
        output_path: Path,
        *,
        ref_text: str | None = None,
        auto_transcribe_reference: bool = False,
    ) -> None:
        calls.append({"ref_text": ref_text, "auto": auto_transcribe_reference})
        output_path.write_bytes(b"x")

    app = create_app(
        output_dir=tmp_path / "outputs",
        sample_dir=tmp_path / "samples",
        translator=fake_translate,
        synthesizer=fake_synthesize,
    )

    response = app.test_client().post(
        "/generate",
        data={
            "text": "Hi",
            "voice": (io.BytesIO(b"a"), "r.webm"),
            "auto_transcribe": "1",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert calls[0]["ref_text"] is None
    assert calls[0]["auto"] is True


def test_synthesize_uses_asr_when_auto(tmp_path: Path) -> None:
    import numpy as np

    from voice_german_cloner.core import synthesize_german_voice

    speaker = tmp_path / "ref.wav"
    speaker.write_bytes(b"fake")
    out = tmp_path / "out.wav"

    mock_model = MagicMock()
    mock_model.generate_voice_clone.return_value = ([np.zeros(8, dtype=np.float32)], 24_000)

    with patch("voice_german_cloner.ref_audio_transcribe.transcribe_reference_audio", return_value="asr text") as tr:
        with patch("voice_german_cloner.core._qwen_clone_model", return_value=mock_model):
            with patch("soundfile.write") as sfw:
                synthesize_german_voice("Hallo", speaker, out, auto_transcribe_reference=True)

    tr.assert_called_once_with(speaker)
    kw = mock_model.generate_voice_clone.call_args[1]
    assert kw["ref_text"] == "asr text"
    assert kw["x_vector_only_mode"] is False
    sfw.assert_called_once()


def test_output_wav_is_served_after_generate(tmp_path: Path) -> None:
    def fake_translate(text: str) -> str:
        return "Hallo"

    def fake_synthesize(
        german_text: str,
        speaker_wav: Path,
        output_path: Path,
        *,
        ref_text: str | None = None,
        auto_transcribe_reference: bool = False,
    ) -> None:
        output_path.write_bytes(b"RIFF")

    app = create_app(
        output_dir=tmp_path / "outputs",
        sample_dir=tmp_path / "samples",
        translator=fake_translate,
        synthesizer=fake_synthesize,
    )
    client = app.test_client()
    post = client.post(
        "/generate",
        data={
            "text": "Hi",
            "voice": (io.BytesIO(b"x"), "a.webm"),
        },
        content_type="multipart/form-data",
    )
    assert post.status_code == 200
    url = post.get_json()["audio_url"]
    get = client.get(url)
    assert get.status_code == 200
    assert get.data == b"RIFF"


def test_generate_requires_text_and_voice(tmp_path: Path) -> None:
    app = create_app(output_dir=tmp_path / "outputs", sample_dir=tmp_path / "samples")

    r1 = app.test_client().post("/generate", data={}, content_type="multipart/form-data")
    assert r1.status_code == 400
    assert "English text is required" in r1.get_json()["error"]

    r2 = app.test_client().post(
        "/generate",
        data={"text": "Hello"},
        content_type="multipart/form-data",
    )
    assert r2.status_code == 400
    assert "voice" in r2.get_json()["error"].lower()


def test_generate_can_use_saved_voice_id(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def fake_translate(text: str) -> str:
        return "Hallo"

    def fake_synthesize(
        german_text: str,
        speaker_wav: Path,
        output_path: Path,
        *,
        ref_text: str | None = None,
        auto_transcribe_reference: bool = False,
    ) -> None:
        calls.append({"speaker": speaker_wav})
        output_path.write_bytes(b"ok")

    app = create_app(
        output_dir=tmp_path / "outputs",
        sample_dir=tmp_path / "samples",
        translator=fake_translate,
        synthesizer=fake_synthesize,
    )
    client = app.test_client()

    save = client.post(
        "/saved-voices",
        data={
            "name": "My voice",
            "voice": (io.BytesIO(b"voice-bytes"), "sample.webm"),
        },
        content_type="multipart/form-data",
    )
    assert save.status_code == 201
    saved_id = save.get_json()["id"]

    response = client.post(
        "/generate",
        data={
            "text": "Hello",
            "saved_voice_id": saved_id,
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert calls
    assert Path(calls[0]["speaker"]).exists()
    assert Path(calls[0]["speaker"]).parent.name == "saved"


def test_saved_voice_crud_endpoints(tmp_path: Path) -> None:
    app = create_app(output_dir=tmp_path / "outputs", sample_dir=tmp_path / "samples")
    client = app.test_client()

    save = client.post(
        "/saved-voices",
        data={
            "name": "Desk Mic",
            "voice": (io.BytesIO(b"abc"), "desk.wav"),
        },
        content_type="multipart/form-data",
    )
    assert save.status_code == 201
    payload = save.get_json()
    assert payload["name"] == "Desk Mic"
    saved_id = payload["id"]

    listed = client.get("/saved-voices")
    assert listed.status_code == 200
    items = listed.get_json()["items"]
    assert any(item["id"] == saved_id and item["name"] == "Desk Mic" for item in items)

    deleted = client.delete(f"/saved-voices/{saved_id}")
    assert deleted.status_code == 200
    listed_after = client.get("/saved-voices")
    assert listed_after.status_code == 200
    items_after = listed_after.get_json()["items"]
    assert all(item["id"] != saved_id for item in items_after)
