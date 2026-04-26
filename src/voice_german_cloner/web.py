from __future__ import annotations

import argparse
import itertools
import json
import threading
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from flask import Flask, jsonify, make_response, render_template_string, request, send_from_directory
from werkzeug.utils import secure_filename

from .core import synthesize_voice, translate_text
from .translation import LANGUAGE_FLOWS, language_name

Translator = Callable[[str, str, str], str]
Synthesizer = Callable[..., Any]

INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Multilingual Voice Cloner</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, -apple-system, sans-serif; }
    body { margin: 0; min-height: 100vh; background: #111827; color: #f9fafb; display: grid; place-items: center; padding: 12px; box-sizing: border-box; }
    main { width: min(1180px, calc(100% - 8px)); height: calc(100vh - 24px); background: #1f2937; border: 1px solid #374151; border-radius: 18px; padding: 16px; box-shadow: 0 20px 60px #0008; display: grid; grid-template-rows: auto 1fr auto; gap: 12px; overflow: hidden; }
    h1 { margin: 0; font-size: 1.5rem; }
    h2 { margin: 0 0 8px; font-size: 1.05rem; }
    h3 { margin: 0 0 8px; font-size: 0.98rem; }
    label { display: block; margin: 10px 0 6px; font-weight: 700; }
    textarea { width: 100%; min-height: 120px; border-radius: 12px; border: 1px solid #4b5563; background: #111827; color: #f9fafb; padding: 12px; font-size: 15px; box-sizing: border-box; }
    #text { min-height: 160px; max-height: 260px; resize: vertical; }
    #refText { min-height: 82px; max-height: 140px; resize: vertical; }
    button { border: 0; border-radius: 999px; padding: 10px 16px; margin: 6px 6px 6px 0; font-weight: 700; cursor: pointer; }
    .primary { background: #22c55e; color: #052e16; }
    .secondary { background: #60a5fa; color: #082f49; }
    .danger { background: #f87171; color: #450a0a; }
    .muted { color: #9ca3af; }
    audio { width: 100%; margin-top: 8px; }
    .card { padding: 12px; background: #111827; border-radius: 12px; border: 1px solid #374151; }
    .hidden { display: none; }
    #status { min-height: 22px; margin: 0; }
    .sample-read { margin-top: 8px; padding: 10px 12px; border-left: 3px solid #4b5563; background: #0f172a; border-radius: 0 10px 10px 0; font-size: 14px; line-height: 1.45; color: #d1d5db; }
    .sample-read strong { color: #e5e7eb; }
    .upload-box { margin-top: 6px; padding: 12px; border: 2px dashed #60a5fa; border-radius: 14px; background: #111827; }
    .upload-box h3 { margin: 0 0 6px; color: #f9fafb; }
    .upload-box .hint { margin: 0 0 12px; font-size: 14px; color: #9ca3af; }
    #voiceFile { display: block; width: 100%; max-width: 100%; padding: 8px 0; font-size: 15px; color: #e5e7eb; }
    #voiceFile::file-selector-button,
    #voiceFile::-webkit-file-upload-button {
      background: #60a5fa; color: #082f49; border: 0; border-radius: 999px; padding: 10px 20px; font-weight: 700; cursor: pointer; margin-right: 14px;
    }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 8px; }
    select, input[type="text"] {
      border-radius: 10px; border: 1px solid #4b5563; background: #111827; color: #f9fafb; padding: 10px; font-size: 14px;
    }
    #savedVoiceSelect { min-width: 260px; }
    .app-header { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
    .app-header p { margin: 0; max-width: 72ch; font-size: 14px; }
    .workspace { min-height: 0; display: grid; grid-template-columns: 0.92fr 1.08fr; gap: 12px; }
    .pane { min-height: 0; overflow: auto; display: grid; gap: 10px; align-content: start; }
    .action-bar { border-top: 1px solid #374151; padding-top: 10px; display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    details.card > summary { cursor: pointer; font-weight: 700; }
    details.card[open] > summary { margin-bottom: 8px; }
    @media (max-width: 980px) {
      main { height: auto; min-height: calc(100vh - 24px); }
      .workspace { grid-template-columns: 1fr; }
      .pane { overflow: visible; }
      .action-bar { flex-direction: column; align-items: flex-start; }
    }
  </style>
</head>
<body>
<main>
  <header class="app-header">
    <h1>Multilingual voice in your voice</h1>
    <p class="muted">Translate between selected local language pairs, or use direct target-language input with <strong><a href="https://github.com/QwenLM/Qwen3-TTS" style="color:#93c5fd;">Qwen3-TTS</a></strong>. Optional transcript/auto-transcribe can improve match.</p>
  </header>

  <div class="workspace">
    <section class="pane">
      <section class="card">
        <h2>1. Voice sample (required)</h2>
        <p class="muted" style="margin:0 0 8px;">About 10–30 seconds, clean speech, no music.</p>

        <div class="upload-box">
          <h3>Upload reference audio</h3>
          <p class="hint"><strong>WAV</strong>, <strong>MP3</strong>, or <strong>M4A</strong> of your voice.</p>
          <input id="voiceFile" type="file" accept=".wav,.mp3,.m4a,audio/wav,audio/wave,audio/x-wav,audio/mpeg,audio/mp3,audio/mp4,audio/x-m4a">
          <audio id="uploadPlayback" controls class="hidden"></audio>
        </div>

        <p class="muted" style="margin:10px 0 0;"><strong>Or record in the browser</strong> (localhost or HTTPS for the mic).</p>
        <p class="sample-read"><strong>Suggested script:</strong> Last Thursday morning, I walked through our quiet neighborhood as the weather shifted from fog to bright sunshine. A neighbor waved, and we chatted briefly about spring travel plans.</p>
        <div class="row">
          <button id="record" class="secondary" type="button">Start recording</button>
          <button id="stop" class="danger" type="button" disabled>Stop recording</button>
        </div>
        <audio id="recordingPlayback" controls class="hidden"></audio>
      </section>

      <section class="card">
        <h2>Saved voices</h2>
        <p class="muted" style="margin:0 0 8px;">Save once and reuse later.</p>
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
      </section>
    </section>

    <section class="pane">
      <form id="generateForm" class="card">
        <h2>2. Text to speak</h2>
        <div class="row">
          <div>
            <label for="sourceLanguage" style="margin-top:0;">Source language</label>
            <select id="sourceLanguage" name="source_language">
              <option value="en" selected>English</option>
              <option value="de">German</option>
              <option value="zh">Chinese</option>
              <option value="es">Spanish</option>
            </select>
          </div>
          <div>
            <label for="targetLanguage" style="margin-top:0;">Target voice language</label>
            <select id="targetLanguage" name="target_language"></select>
          </div>
        </div>
        <p id="languageHint" class="muted" style="margin:8px 0 0;">English → German</p>
        <label for="text" id="textLabel">English text</label>
        <textarea id="text" name="text" placeholder="Good morning, how are you?" required></textarea>
        <label class="muted" style="margin-top:8px;display:flex;align-items:flex-start;gap:10px;font-weight:600;cursor:pointer;">
          <input type="checkbox" id="skipTranslation" name="skip_translation" value="1" style="width:auto;margin-top:4px;">
          <span>Text is already in target language (skip translation).</span>
        </label>
      </form>

      <details class="card">
        <summary>Reference transcript (optional)</summary>
        <p class="muted" style="margin:6px 0 8px;">Paste the exact words from your reference clip for better timbre matching.</p>
        <label for="refText">Transcript of reference audio</label>
        <textarea id="refText" name="ref_text" rows="4" placeholder="Leave empty for embedding-only mode, or paste what you said…"></textarea>
        <label class="muted" style="margin-top:10px;display:flex;align-items:flex-start;gap:10px;font-weight:600;cursor:pointer;">
          <input type="checkbox" id="autoTranscribe" name="auto_transcribe" value="1" style="width:auto;margin-top:4px;">
          <span>Auto-transcribe reference with Whisper (English).</span>
        </label>
        <label for="asrModel" style="margin-top:8px;">Whisper model</label>
        <select id="asrModel" name="asr_model">
          <option value="openai/whisper-tiny" selected>openai/whisper-tiny (default, fastest)</option>
          <option value="openai/whisper-base">openai/whisper-base</option>
          <option value="openai/whisper-small">openai/whisper-small</option>
        </select>
      </details>

      <div>
        <button class="primary" type="submit" form="generateForm">Generate voice</button>
      </div>

      <section id="result" class="card hidden">
        <h2>Result</h2>
        <p><strong id="targetLanguageLabel">Generated text:</strong> <span id="generatedText"></span></p>
        <audio id="voicePlayback" controls></audio>
      </section>
    </section>
  </div>

  <div class="action-bar">
    <p id="status" class="muted"></p>
  </div>
</main>
<script>
let recorder;
let chunks = [];
/** @type {null | {blob: Blob, filename: string}} */
let voiceForSubmit = null;
let uploadObjectUrl = null;
let activeGeneratePoll = null;

const recordButton = document.getElementById('record');
const stopButton = document.getElementById('stop');
const recordingPlayback = document.getElementById('recordingPlayback');
const voiceFileInput = document.getElementById('voiceFile');
const uploadPlayback = document.getElementById('uploadPlayback');
const statusEl = document.getElementById('status');
const form = document.getElementById('generateForm');
const result = document.getElementById('result');
const generatedText = document.getElementById('generatedText');
const targetLanguageLabel = document.getElementById('targetLanguageLabel');
const voicePlayback = document.getElementById('voicePlayback');
const saveVoiceName = document.getElementById('saveVoiceName');
const saveCurrentVoiceBtn = document.getElementById('saveCurrentVoice');
const savedVoiceSelect = document.getElementById('savedVoiceSelect');
const refreshSavedVoicesBtn = document.getElementById('refreshSavedVoices');
const deleteSavedVoiceBtn = document.getElementById('deleteSavedVoice');
const sourceLanguage = document.getElementById('sourceLanguage');
const targetLanguage = document.getElementById('targetLanguage');
const languageHint = document.getElementById('languageHint');
const textInput = document.getElementById('text');
const textLabel = document.getElementById('textLabel');
const skipTranslation = document.getElementById('skipTranslation');

const languageNames = {
  en: 'English',
  de: 'German',
  zh: 'Chinese',
  es: 'Spanish',
};

const supportedTargets = {
  en: ['de', 'zh', 'en', 'es'],
  de: ['de', 'en'],
  zh: ['zh', 'en'],
  es: ['en', 'es'],
};

const sourceCopy = {
  en: ['English text', 'Good morning, how are you?'],
  de: ['German text', 'Guten Morgen, wie geht es dir?'],
  zh: ['Chinese text', '早上好，你好吗？'],
  es: ['Spanish text', 'Buenos dias, como estas?'],
};

function updateLanguageSelectors() {
  const source = sourceLanguage.value;
  const previousTarget = targetLanguage.value;
  const targets = supportedTargets[source] || [];
  targetLanguage.innerHTML = '';
  for (const target of targets) {
    const option = document.createElement('option');
    option.value = target;
    option.textContent =
      source === target
        ? languageNames[target] + ' direct (no translation)'
        : languageNames[target];
    targetLanguage.appendChild(option);
  }
  targetLanguage.value = targets.includes(previousTarget) ? previousTarget : targets[0];
  const copy = sourceCopy[source] || sourceCopy.en;
  textLabel.textContent = copy[0];
  textInput.placeholder = copy[1];
  updateLanguageHintAndInputText();
}

function updateLanguageHintAndInputText() {
  const source = sourceLanguage.value;
  const target = targetLanguage.value;
  const shouldSkipTranslation = !!(skipTranslation && skipTranslation.checked);
  if (shouldSkipTranslation) {
    languageHint.textContent = 'Direct ' + languageNames[target] + ' text mode (no translation)';
    textLabel.textContent = languageNames[target] + ' text';
    const targetCopy = sourceCopy[target] || sourceCopy.en;
    textInput.placeholder = targetCopy[1];
    return;
  }
  const copy = sourceCopy[source] || sourceCopy.en;
  textLabel.textContent = copy[0];
  textInput.placeholder = copy[1];
  languageHint.textContent =
    source === target
      ? languageNames[target] + ' direct (no translation)'
      : languageNames[source] + ' → ' + languageNames[target];
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

function stopGeneratePolling() {
  if (activeGeneratePoll) {
    clearInterval(activeGeneratePoll);
    activeGeneratePoll = null;
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
  stopGeneratePolling();
  const savedVoiceId = savedVoiceSelect.value;
  if (!voiceForSubmit && !savedVoiceId) {
    statusEl.textContent = 'Record/upload a voice, or select a saved voice first.';
    return;
  }

  const data = new FormData();
  data.append('text', textInput.value);
  data.append('source_language', sourceLanguage.value);
  data.append('target_language', targetLanguage.value);
  data.append('language_flow', sourceLanguage.value + '-' + targetLanguage.value);
  if (skipTranslation && skipTranslation.checked) {
    data.append('skip_translation', '1');
  }
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

  const isDirect = sourceLanguage.value === targetLanguage.value || (skipTranslation && skipTranslation.checked);
  statusEl.textContent =
    isDirect
      ? 'Generating audio directly. First run can take several minutes while models download...'
      : 'Translating and generating audio. First run can take several minutes while models download...';
  result.classList.add('hidden');

  try {
    const response = await fetch('/generate', { method: 'POST', body: data });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Generation failed');
    if (!payload.job_id) throw new Error('Generation job was not created.');

    const pollStatus = async () => {
      try {
        const statusResponse = await fetch('/generate-status/' + encodeURIComponent(payload.job_id));
        const statusPayload = await statusResponse.json();
        if (!statusResponse.ok) throw new Error(statusPayload.error || 'Failed to load generation status');
        if (statusPayload.status_message) statusEl.textContent = statusPayload.status_message;

        if (statusPayload.status === 'done') {
          stopGeneratePolling();
          targetLanguageLabel.textContent = (statusPayload.target_language_name || 'Generated') + ':';
          generatedText.textContent = statusPayload.target_text || '';
          voicePlayback.src = statusPayload.audio_url + '?t=' + Date.now();
          result.classList.remove('hidden');
        } else if (statusPayload.status === 'error') {
          stopGeneratePolling();
          throw new Error(statusPayload.error || 'Generation failed');
        }
      } catch (error) {
        stopGeneratePolling();
        statusEl.textContent = error.message;
      }
    };

    await pollStatus();
    if (!activeGeneratePoll) {
      activeGeneratePoll = setInterval(pollStatus, 1000);
    }
  } catch (error) {
    stopGeneratePolling();
    statusEl.textContent = error.message;
  }
});

loadSavedVoices();
sourceLanguage.addEventListener('change', updateLanguageSelectors);
targetLanguage.addEventListener('change', updateLanguageSelectors);
skipTranslation.addEventListener('change', updateLanguageHintAndInputText);
updateLanguageSelectors();
</script>
</body>
</html>
"""


def create_app(
    output_dir: Path | str = "outputs",
    sample_dir: Path | str = "voice_samples",
    translator: Translator = translate_text,
    synthesizer: Synthesizer = synthesize_voice,
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
    jobs_lock = threading.Lock()
    jobs: dict[str, dict[str, Any]] = {}

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

    def resolve_language_flow() -> tuple[str, str, str]:
        source_language = request.form.get("source_language", "").strip().lower()
        target_language = request.form.get("target_language", "").strip().lower()
        if source_language or target_language:
            language_flow = f"{source_language}-{target_language}"
            try:
                flow = LANGUAGE_FLOWS[language_flow]
                return flow.source_language, flow.target_language, flow.label
            except KeyError as exc:
                supported = ", ".join(LANGUAGE_FLOWS)
                raise ValueError(
                    f"Language pair must be one of the supported flows: {supported}."
                ) from exc

        language_flow = request.form.get("language_flow", "").strip().lower()
        if not language_flow:
            # Backward compatibility for the earlier English/German-only form.
            text_language = request.form.get("text_language", "en").strip().lower() or "en"
            language_flow = "de-de" if text_language == "de" else "en-de"
        try:
            flow = LANGUAGE_FLOWS[language_flow]
            return flow.source_language, flow.target_language, flow.label
        except KeyError as exc:
            supported = ", ".join(LANGUAGE_FLOWS)
            raise ValueError(f"Language flow must be one of: {supported}.") from exc

    @app.get("/")
    def index():
        resp = make_response(render_template_string(INDEX_HTML))
        resp.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
        return resp

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,DELETE,OPTIONS"
        return response

    @app.get("/health")
    def health():
        return jsonify(ok=True)

    @app.post("/generate")
    def generate():
        text = request.form.get("text", "").strip()
        voice = request.files.get("voice")
        saved_voice_id = request.form.get("saved_voice_id", "").strip()
        skip_translation = request.form.get("skip_translation", "").lower() in (
            "1",
            "on",
            "true",
            "yes",
        )

        try:
            source_language, target_language, flow_label = resolve_language_flow()
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        if not text:
            return jsonify(error=f"{language_name(source_language)} text is required."), 400

        number = next(counter)
        output_file = output_path / f"voice_{target_language}_{number:03d}.wav"
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

        job_id = uuid4().hex
        with jobs_lock:
            jobs[job_id] = {
                "status": "queued",
                "status_message": "Queued...",
                "source_text": text,
                "source_language": source_language,
                "target_language": target_language,
                "source_language_name": language_name(source_language),
                "target_language_name": language_name(target_language),
                "language_flow": flow_label,
                "audio_url": f"/outputs/{output_file.name}",
            }

        def update_job(**updates: Any) -> None:
            with jobs_lock:
                if job_id in jobs:
                    jobs[job_id].update(updates)

        def run_job() -> None:
            try:
                if skip_translation or source_language == target_language:
                    update_job(
                        status="generating",
                        status_message=(
                            "Using provided target-language text. Generating voice..."
                            if skip_translation and source_language != target_language
                            else "Generating voice..."
                        ),
                    )
                    target_text = text
                else:
                    update_job(
                        status="translating",
                        status_message=f"Translating {language_name(source_language)} to {language_name(target_language)}...",
                    )
                    target_text = translator(text, source_language, target_language)
                    update_job(
                        status="generating",
                        status_message="Generating voice...",
                    )

                synthesizer(
                    target_text,
                    speaker_file,
                    output_file,
                    language=language_name(target_language),
                    ref_text=ref_text_raw,
                    auto_transcribe_reference=auto_tc,
                    asr_model=asr_model,
                )
                update_job(
                    status="done",
                    status_message="Done.",
                    target_text=target_text,
                )
            except Exception as exc:  # noqa: BLE001 - display error to local user
                update_job(
                    status="error",
                    status_message=str(exc),
                    error=str(exc),
                )

        threading.Thread(target=run_job, daemon=True).start()
        return jsonify(job_id=job_id, status="queued")

    @app.get("/generate-status/<job_id>")
    def generate_status(job_id: str):
        with jobs_lock:
            payload = jobs.get(job_id)
        if payload is None:
            return jsonify(error="Generation job was not found."), 404
        return jsonify(payload)

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


def run_web_server(
    *,
    host: str = "0.0.0.0",
    port: int = 7860,
    output_dir: str | Path = "outputs",
    sample_dir: str | Path = "voice_samples",
    debug: bool = False,
) -> None:
    app = create_app(output_dir=output_dir, sample_dir=sample_dir)
    app.run(host=host, port=port, debug=debug)


def build_web_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local voice cloning Flask API/web UI.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--sample-dir", default="voice_samples")
    parser.add_argument("--debug", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_web_parser().parse_args(argv)
    run_web_server(
        host=args.host,
        port=args.port,
        output_dir=args.output_dir,
        sample_dir=args.sample_dir,
        debug=bool(args.debug),
    )


if __name__ == "__main__":
    main()
