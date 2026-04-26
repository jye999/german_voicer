from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from flask import Flask, jsonify, make_response, render_template_string, request, send_from_directory
from werkzeug.utils import secure_filename

from .core import synthesize_german_voice, translate_english_to_german

Translator = Callable[[str], str]
Synthesizer = Callable[..., Any]

INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>German Voice Cloner</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, -apple-system, sans-serif; }
    body { margin: 0; min-height: 100vh; background: #111827; color: #f9fafb; display: grid; place-items: center; }
    main { width: min(760px, calc(100% - 32px)); background: #1f2937; border: 1px solid #374151; border-radius: 18px; padding: 28px; box-shadow: 0 20px 60px #0008; }
    h1 { margin-top: 0; }
    label { display: block; margin: 18px 0 8px; font-weight: 700; }
    textarea { width: 100%; min-height: 130px; border-radius: 12px; border: 1px solid #4b5563; background: #111827; color: #f9fafb; padding: 12px; font-size: 16px; box-sizing: border-box; }
    button { border: 0; border-radius: 999px; padding: 12px 18px; margin: 8px 8px 8px 0; font-weight: 700; cursor: pointer; }
    .primary { background: #22c55e; color: #052e16; }
    .secondary { background: #60a5fa; color: #082f49; }
    .danger { background: #f87171; color: #450a0a; }
    .muted { color: #9ca3af; }
    audio { width: 100%; margin-top: 10px; }
    .card { margin-top: 18px; padding: 16px; background: #111827; border-radius: 12px; border: 1px solid #374151; }
    .hidden { display: none; }
    #status { min-height: 24px; }
    .sample-read { margin-top: 14px; padding: 12px 14px; border-left: 3px solid #4b5563; background: #0f172a; border-radius: 0 10px 10px 0; font-size: 15px; line-height: 1.55; color: #d1d5db; }
    .sample-read strong { color: #e5e7eb; }
    .upload-box { margin-top: 8px; padding: 16px; border: 2px dashed #60a5fa; border-radius: 14px; background: #111827; }
    .upload-box h3 { margin: 0 0 10px; font-size: 1.05rem; color: #f9fafb; }
    .upload-box .hint { margin: 0 0 12px; font-size: 14px; color: #9ca3af; }
    #voiceFile { display: block; width: 100%; max-width: 100%; padding: 8px 0; font-size: 15px; color: #e5e7eb; }
    #voiceFile::file-selector-button,
    #voiceFile::-webkit-file-upload-button {
      background: #60a5fa; color: #082f49; border: 0; border-radius: 999px; padding: 10px 20px; font-weight: 700; cursor: pointer; margin-right: 14px;
    }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 10px; }
    select, input[type="text"] {
      border-radius: 10px; border: 1px solid #4b5563; background: #111827; color: #f9fafb; padding: 10px; font-size: 14px;
    }
    #savedVoiceSelect { min-width: 260px; }
  </style>
</head>
<body>
<main>
  <h1>German voice in your voice</h1>
  <p class="muted">Translate English→German locally, or enter German directly, then use <strong><a href="https://github.com/QwenLM/Qwen3-TTS" style="color:#93c5fd;">Qwen3-TTS</a> Base</strong> voice clone. Optional: paste a transcript of your reference clip or use auto-transcribe (Whisper) for stronger ICL cloning. Without that, only the speaker embedding is used. GPU recommended.</p>

  <section class="card">
    <h2>1. Voice sample (required)</h2>
    <p class="muted">About 10–30 seconds, clean speech, no music. Upload <strong>or</strong> record in the browser.</p>

    <div class="upload-box">
      <h3>Upload reference audio</h3>
      <p class="hint"><strong>WAV</strong>, <strong>MP3</strong>, or <strong>M4A</strong> of your voice.</p>
      <input id="voiceFile" type="file" accept=".wav,.mp3,.m4a,audio/wav,audio/wave,audio/x-wav,audio/mpeg,audio/mp3,audio/mp4,audio/x-m4a">
      <audio id="uploadPlayback" controls class="hidden"></audio>
    </div>

    <p class="muted" style="margin-top: 22px;"><strong>Or record in the browser</strong> (localhost or HTTPS for the mic).</p>
    <p class="sample-read"><strong>Suggested script (read in your normal voice):</strong>
    Last Thursday morning, I walked through our quiet neighborhood as the weather shifted from fog to bright sunshine. A neighbor waved, and we chatted briefly about spring travel plans.</p>
    <button id="record" class="secondary" type="button">Start recording</button>
    <button id="stop" class="danger" type="button" disabled>Stop recording</button>
    <audio id="recordingPlayback" controls class="hidden"></audio>

    <div class="card" style="margin-top:16px;">
      <h3 style="margin:0 0 10px;">Saved voices</h3>
      <p class="muted" style="margin-top:0;">Save your current uploaded/recorded sample once, then reuse it later.</p>
      <div class="row">
        <input id="saveVoiceName" type="text" placeholder="Voice name (e.g. My Desk Mic)">
        <button id="saveCurrentVoice" class="secondary" type="button">Save current sample</button>
      </div>
      <div class="row">
        <select id="savedVoiceSelect">
          <option value="">No saved voice selected</option>
        </select>
        <button id="refreshSavedVoices" class="secondary" type="button">Refresh</button>
        <button id="deleteSavedVoice" class="danger" type="button">Delete selected</button>
      </div>
      <p class="muted" style="margin:10px 0 0;">Tip: If a saved voice is selected and no new file is chosen, generation uses the saved voice.</p>
    </div>
  </section>

  <form id="generateForm" class="card">
    <h2>2. Reference transcript (optional)</h2>
    <p class="muted">For <strong>better timbre match</strong>, paste the exact words you spoke in the reference recording (same language as the clip, often English if you used the script below).</p>
    <label for="refText">Transcript of reference audio</label>
    <textarea id="refText" name="ref_text" rows="4" placeholder="Leave empty for embedding-only mode, or paste what you said…"></textarea>
    <label class="muted" style="margin-top:14px;display:flex;align-items:flex-start;gap:10px;font-weight:600;cursor:pointer;">
      <input type="checkbox" id="autoTranscribe" name="auto_transcribe" value="1" style="width:auto;margin-top:4px;">
      <span>Auto-transcribe reference with Whisper (English). Uses the first run to download the ASR model. Ignored if you filled the transcript above.</span>
    </label>
    <label for="asrModel" style="margin-top:10px;">Whisper model (for Auto-transcribe)</label>
    <select id="asrModel" name="asr_model">
      <option value="openai/whisper-tiny" selected>openai/whisper-tiny (default, fastest)</option>
      <option value="openai/whisper-base">openai/whisper-base</option>
      <option value="openai/whisper-small">openai/whisper-small</option>
    </select>

    <h2 style="margin-top:22px;">3. Text to speak</h2>
    <label for="textLanguage">Text language</label>
    <select id="textLanguage" name="text_language">
      <option value="en" selected>English (translate to German)</option>
      <option value="de">German (speak without translating)</option>
    </select>
    <label for="text" id="textLabel">English text</label>
    <textarea id="text" name="text" placeholder="Good morning, how are you?" required></textarea>
    <button class="primary" type="submit">Generate German voice</button>
  </form>

  <section id="result" class="card hidden">
    <h2>Result</h2>
    <p><strong>German:</strong> <span id="german"></span></p>
    <audio id="germanPlayback" controls></audio>
  </section>

  <p id="status" class="muted"></p>
</main>
<script>
let recorder;
let chunks = [];
/** @type {null | {blob: Blob, filename: string}} */
let voiceForSubmit = null;
let uploadObjectUrl = null;

const recordButton = document.getElementById('record');
const stopButton = document.getElementById('stop');
const recordingPlayback = document.getElementById('recordingPlayback');
const voiceFileInput = document.getElementById('voiceFile');
const uploadPlayback = document.getElementById('uploadPlayback');
const statusEl = document.getElementById('status');
const form = document.getElementById('generateForm');
const result = document.getElementById('result');
const german = document.getElementById('german');
const germanPlayback = document.getElementById('germanPlayback');
const saveVoiceName = document.getElementById('saveVoiceName');
const saveCurrentVoiceBtn = document.getElementById('saveCurrentVoice');
const savedVoiceSelect = document.getElementById('savedVoiceSelect');
const refreshSavedVoicesBtn = document.getElementById('refreshSavedVoices');
const deleteSavedVoiceBtn = document.getElementById('deleteSavedVoice');
const textLanguage = document.getElementById('textLanguage');
const textInput = document.getElementById('text');
const textLabel = document.getElementById('textLabel');

function updateTextLanguageCopy() {
  if (textLanguage.value === 'de') {
    textLabel.textContent = 'German text';
    textInput.placeholder = 'Guten Morgen, wie geht es dir?';
    return;
  }
  textLabel.textContent = 'English text';
  textInput.placeholder = 'Good morning, how are you?';
}

function setSavedVoiceOptions(items) {
  savedVoiceSelect.innerHTML = '';
  const noneOption = document.createElement('option');
  noneOption.value = '';
  noneOption.textContent = 'No saved voice selected';
  savedVoiceSelect.appendChild(noneOption);
  for (const item of items) {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.name;
    savedVoiceSelect.appendChild(option);
  }
}

async function loadSavedVoices() {
  try {
    const response = await fetch('/saved-voices');
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Failed to load saved voices');
    setSavedVoiceOptions(payload.items || []);
  } catch (error) {
    statusEl.textContent = error.message;
  }
}

function getMicStream() {
  const constraints = { audio: true };
  if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function') {
    return navigator.mediaDevices.getUserMedia(constraints);
  }
  const legacy =
    navigator.getUserMedia ||
    navigator.webkitGetUserMedia ||
    navigator.mozGetUserMedia ||
    navigator.msGetUserMedia;
  if (typeof legacy === 'function') {
    return new Promise((resolve, reject) => {
      legacy.call(navigator, constraints, resolve, reject);
    });
  }
  return Promise.reject(
    new Error(
      'This page is not a secure context, so the browser hides the microphone API. ' +
        'Open http://127.0.0.1:7860 or http://localhost:7860 on the machine running the server, ' +
        'or serve the app over HTTPS.',
    ),
  );
}

if (!window.isSecureContext && location.hostname !== '127.0.0.1' && location.hostname !== 'localhost') {
  statusEl.textContent =
    "Tip: For browser recording, use http://127.0.0.1:7860 (or HTTPS). Plain HTTP to this machine's LAN IP usually blocks the microphone.";
}

recordButton.addEventListener('click', async () => {
  try {
    const stream = await getMicStream();
    chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = event => chunks.push(event.data);
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
      voiceForSubmit = { blob, filename: 'recording.webm' };
      voiceFileInput.value = '';
      if (uploadObjectUrl) {
        URL.revokeObjectURL(uploadObjectUrl);
        uploadObjectUrl = null;
      }
      uploadPlayback.classList.add('hidden');
      recordingPlayback.src = URL.createObjectURL(blob);
      recordingPlayback.classList.remove('hidden');
      stream.getTracks().forEach(track => track.stop());
      statusEl.textContent = 'Recording ready. Enter text and generate.';
    };
    recorder.start();
    recordButton.disabled = true;
    stopButton.disabled = false;
    statusEl.textContent = 'Recording...';
  } catch (error) {
    statusEl.textContent = 'Microphone access failed: ' + error.message;
  }
});

stopButton.addEventListener('click', () => {
  if (recorder && recorder.state !== 'inactive') recorder.stop();
  recordButton.disabled = false;
  stopButton.disabled = true;
});

voiceFileInput.addEventListener('change', () => {
  const file = voiceFileInput.files && voiceFileInput.files[0];
  if (!file) return;
  const lower = file.name.toLowerCase();
  if (!lower.endsWith('.wav') && !lower.endsWith('.mp3') && !lower.endsWith('.m4a')) {
    statusEl.textContent = 'Please choose a .wav, .mp3, or .m4a file.';
    voiceFileInput.value = '';
    return;
  }
  voiceForSubmit = { blob: file, filename: file.name };
  if (uploadObjectUrl) URL.revokeObjectURL(uploadObjectUrl);
  uploadObjectUrl = URL.createObjectURL(file);
  uploadPlayback.src = uploadObjectUrl;
  uploadPlayback.classList.remove('hidden');
  recordingPlayback.pause();
  recordingPlayback.removeAttribute('src');
  recordingPlayback.classList.add('hidden');
  statusEl.textContent = 'Using uploaded file: ' + file.name;
});

saveCurrentVoiceBtn.addEventListener('click', async () => {
  if (!voiceForSubmit) {
    statusEl.textContent = 'Upload or record a sample first, then save it.';
    return;
  }
  const name = (saveVoiceName.value || '').trim();
  if (!name) {
    statusEl.textContent = 'Enter a name for the saved voice.';
    return;
  }
  const data = new FormData();
  data.append('name', name);
  data.append('voice', voiceForSubmit.blob, voiceForSubmit.filename);
  try {
    const response = await fetch('/saved-voices', { method: 'POST', body: data });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Failed to save voice');
    statusEl.textContent = 'Saved voice: ' + payload.name;
    await loadSavedVoices();
    if (payload.id) savedVoiceSelect.value = payload.id;
    saveVoiceName.value = '';
  } catch (error) {
    statusEl.textContent = error.message;
  }
});

refreshSavedVoicesBtn.addEventListener('click', async () => {
  await loadSavedVoices();
  statusEl.textContent = 'Saved voices refreshed.';
});

deleteSavedVoiceBtn.addEventListener('click', async () => {
  const voiceId = savedVoiceSelect.value;
  if (!voiceId) {
    statusEl.textContent = 'Select a saved voice to delete.';
    return;
  }
  try {
    const response = await fetch('/saved-voices/' + encodeURIComponent(voiceId), { method: 'DELETE' });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Failed to delete saved voice');
    statusEl.textContent = 'Deleted saved voice.';
    await loadSavedVoices();
  } catch (error) {
    statusEl.textContent = error.message;
  }
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  const savedVoiceId = savedVoiceSelect.value;
  if (!voiceForSubmit && !savedVoiceId) {
    statusEl.textContent = 'Record/upload a voice, or select a saved voice first.';
    return;
  }

  const data = new FormData();
  data.append('text', textInput.value);
  data.append('text_language', textLanguage.value);
  if (voiceForSubmit) {
    data.append('voice', voiceForSubmit.blob, voiceForSubmit.filename);
  } else if (savedVoiceId) {
    data.append('saved_voice_id', savedVoiceId);
  }
  const refEl = document.getElementById('refText');
  if (refEl && refEl.value.trim()) {
    data.append('ref_text', refEl.value.trim());
  }
  if (document.getElementById('autoTranscribe') && document.getElementById('autoTranscribe').checked) {
    data.append('auto_transcribe', '1');
    const asrModelEl = document.getElementById('asrModel');
    if (asrModelEl && asrModelEl.value) {
      data.append('asr_model', asrModelEl.value);
    }
  }

  statusEl.textContent =
    textLanguage.value === 'de'
      ? 'Generating audio from German text. First run can take several minutes while models download...'
      : 'Translating and generating audio. First run can take several minutes while models download...';
  result.classList.add('hidden');

  try {
    const response = await fetch('/generate', { method: 'POST', body: data });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Generation failed');
    german.textContent = payload.german;
    germanPlayback.src = payload.audio_url + '?t=' + Date.now();
    result.classList.remove('hidden');
    statusEl.textContent = 'Done.';
  } catch (error) {
    statusEl.textContent = error.message;
  }
});

loadSavedVoices();
textLanguage.addEventListener('change', updateTextLanguageCopy);
updateTextLanguageCopy();
</script>
</body>
</html>
"""


def create_app(
    output_dir: Path | str = "outputs",
    sample_dir: Path | str = "voice_samples",
    translator: Translator = translate_english_to_german,
    synthesizer: Synthesizer = synthesize_german_voice,
) -> Flask:
    app = Flask(__name__)
    output_path = Path(output_dir).expanduser().resolve()
    sample_path = Path(sample_dir).expanduser().resolve()
    saved_path = sample_path / "saved"
    saved_index_path = saved_path / "index.json"
    output_path.mkdir(parents=True, exist_ok=True)
    sample_path.mkdir(parents=True, exist_ok=True)
    saved_path.mkdir(parents=True, exist_ok=True)
    if not saved_index_path.exists():
        saved_index_path.write_text("[]", encoding="utf-8")
    counter = itertools.count(1)

    def load_saved_index() -> list[dict[str, str]]:
        try:
            data = json.loads(saved_index_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except Exception:
            pass
        return []

    def save_saved_index(items: list[dict[str, str]]) -> None:
        saved_index_path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def find_saved_voice(voice_id: str) -> dict[str, str] | None:
        for item in load_saved_index():
            if item.get("id") == voice_id:
                return item
        return None

    @app.get("/")
    def index():
        resp = make_response(render_template_string(INDEX_HTML))
        resp.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
        return resp

    @app.post("/generate")
    def generate():
        text = request.form.get("text", "").strip()
        text_language = request.form.get("text_language", "en").strip().lower() or "en"
        voice = request.files.get("voice")
        saved_voice_id = request.form.get("saved_voice_id", "").strip()

        if text_language not in {"en", "de"}:
            return jsonify(error="Text language must be 'en' or 'de'."), 400
        if not text:
            required_language = "German" if text_language == "de" else "English"
            return jsonify(error=f"{required_language} text is required."), 400

        number = next(counter)
        output_file = output_path / f"german_voice_{number:03d}.wav"
        if voice is not None and voice.filename:
            extension = Path(secure_filename(voice.filename)).suffix or ".webm"
            speaker_file = sample_path / f"recording_{number:03d}{extension}"
            voice.save(speaker_file)
        elif saved_voice_id:
            saved_voice = find_saved_voice(saved_voice_id)
            if not saved_voice:
                return jsonify(error="Saved voice was not found."), 400
            speaker_file = saved_path / saved_voice["filename"]
            if not speaker_file.exists():
                return jsonify(error="Saved voice file is missing. Please re-save it."), 400
        else:
            return jsonify(error="A voice recording, uploaded reference file, or saved voice is required for cloning."), 400

        ref_text_raw = request.form.get("ref_text", "").strip() or None
        auto_tc = request.form.get("auto_transcribe", "").lower() in ("1", "on", "true", "yes")
        asr_model = request.form.get("asr_model", "").strip() or None

        try:
            german_text = text if text_language == "de" else translator(text)
            synthesizer(
                german_text,
                speaker_file,
                output_file,
                ref_text=ref_text_raw,
                auto_transcribe_reference=auto_tc,
                asr_model=asr_model,
            )
        except Exception as exc:  # noqa: BLE001 - display error to local user
            return jsonify(error=str(exc)), 500

        return jsonify(
            english=text if text_language == "en" else None,
            german=german_text,
            audio_url=f"/outputs/{output_file.name}",
        )

    @app.get("/saved-voices")
    def list_saved_voices():
        return jsonify(items=load_saved_index())

    @app.post("/saved-voices")
    def save_voice():
        name = request.form.get("name", "").strip()
        voice = request.files.get("voice")
        if not name:
            return jsonify(error="Voice name is required."), 400
        if voice is None or voice.filename == "":
            return jsonify(error="Voice file is required."), 400

        extension = Path(secure_filename(voice.filename)).suffix or ".webm"
        voice_id = uuid4().hex
        filename = f"{voice_id}{extension}"
        voice.save(saved_path / filename)

        items = load_saved_index()
        items.append({"id": voice_id, "name": name, "filename": filename})
        save_saved_index(items)
        return jsonify(id=voice_id, name=name, filename=filename), 201

    @app.delete("/saved-voices/<voice_id>")
    def delete_saved_voice(voice_id: str):
        items = load_saved_index()
        item = next((i for i in items if i.get("id") == voice_id), None)
        if item is None:
            return jsonify(error="Saved voice was not found."), 404
        voice_file = saved_path / item.get("filename", "")
        if voice_file.exists():
            voice_file.unlink()
        remaining = [i for i in items if i.get("id") != voice_id]
        save_saved_index(remaining)
        return jsonify(ok=True)

    @app.get("/outputs/<path:filename>")
    def output_file(filename: str):
        return send_from_directory(output_path, filename, as_attachment=False)

    return app


def main() -> None:
    app = create_app()
    app.run(host="0.0.0.0", port=7860, debug=True)


if __name__ == "__main__":
    main()
