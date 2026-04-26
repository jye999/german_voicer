let voiceForSubmit = null;
let uploadObjectUrl = null;
let activeGeneratePoll = null;
let backendBaseUrl = "";
let recorder = null;
let chunks = [];

const recordButton = document.getElementById("record");
const stopButton = document.getElementById("stop");
const recordingPlayback = document.getElementById("recordingPlayback");
const voiceFileInput = document.getElementById("voiceFile");
const uploadPlayback = document.getElementById("uploadPlayback");
const statusEl = document.getElementById("status");
const backendInfo = document.getElementById("backendInfo");
const form = document.getElementById("generateForm");
const result = document.getElementById("result");
const generatedText = document.getElementById("generatedText");
const targetLanguageLabel = document.getElementById("targetLanguageLabel");
const voicePlayback = document.getElementById("voicePlayback");
const saveVoiceName = document.getElementById("saveVoiceName");
const saveCurrentVoiceBtn = document.getElementById("saveCurrentVoice");
const savedVoiceSelect = document.getElementById("savedVoiceSelect");
const refreshSavedVoicesBtn = document.getElementById("refreshSavedVoices");
const deleteSavedVoiceBtn = document.getElementById("deleteSavedVoice");
const sourceLanguage = document.getElementById("sourceLanguage");
const targetLanguage = document.getElementById("targetLanguage");
const languageHint = document.getElementById("languageHint");
const textInput = document.getElementById("text");
const textLabel = document.getElementById("textLabel");
const skipTranslation = document.getElementById("skipTranslation");

const languageNames = { en: "English", de: "German", zh: "Chinese", es: "Spanish" };
const supportedTargets = { en: ["de", "zh", "en", "es"], de: ["de", "en"], zh: ["zh", "en"], es: ["en", "es"] };
const sourceCopy = {
  en: ["English text", "Good morning, how are you?"],
  de: ["German text", "Guten Morgen, wie geht es dir?"],
  zh: ["Chinese text", "早上好，你好吗？"],
  es: ["Spanish text", "Buenos dias, como estas?"],
};

function apiUrl(path) {
  return `${backendBaseUrl}${path}`;
}

async function resolveBackendBaseUrl() {
  const tauri = window.__TAURI__;
  if (!tauri || !tauri.core || typeof tauri.core.invoke !== "function") {
    backendBaseUrl = "http://127.0.0.1:7860";
    backendInfo.textContent = `Backend: ${backendBaseUrl}`;
    return;
  }
  backendBaseUrl = await tauri.core.invoke("get_backend_url");
  backendInfo.textContent = `Backend: ${backendBaseUrl}`;
}

function getMicStream() {
  const constraints = { audio: true };
  if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === "function") {
    return navigator.mediaDevices.getUserMedia(constraints);
  }
  return Promise.reject(new Error("Microphone API is not available in this environment."));
}

function updateLanguageHintAndInputText() {
  const source = sourceLanguage.value;
  const target = targetLanguage.value;
  if (skipTranslation.checked) {
    languageHint.textContent = `Direct ${languageNames[target]} text mode (no translation)`;
    textLabel.textContent = `${languageNames[target]} text`;
    textInput.placeholder = (sourceCopy[target] || sourceCopy.en)[1];
    return;
  }
  textLabel.textContent = (sourceCopy[source] || sourceCopy.en)[0];
  textInput.placeholder = (sourceCopy[source] || sourceCopy.en)[1];
  languageHint.textContent = source === target ? `${languageNames[target]} direct (no translation)` : `${languageNames[source]} -> ${languageNames[target]}`;
}

function updateLanguageSelectors() {
  const source = sourceLanguage.value;
  const previousTarget = targetLanguage.value;
  const targets = supportedTargets[source] || [];
  targetLanguage.innerHTML = "";
  for (const target of targets) {
    const option = document.createElement("option");
    option.value = target;
    option.textContent = source === target ? `${languageNames[target]} direct (no translation)` : languageNames[target];
    targetLanguage.appendChild(option);
  }
  targetLanguage.value = targets.includes(previousTarget) ? previousTarget : targets[0];
  updateLanguageHintAndInputText();
}

function stopGeneratePolling() {
  if (activeGeneratePoll) {
    clearInterval(activeGeneratePoll);
    activeGeneratePoll = null;
  }
}

function setSavedVoiceOptions(items) {
  savedVoiceSelect.innerHTML = "";
  const noneOption = document.createElement("option");
  noneOption.value = "";
  noneOption.textContent = "No saved voice selected";
  savedVoiceSelect.appendChild(noneOption);
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.name;
    savedVoiceSelect.appendChild(option);
  }
}

async function loadSavedVoices() {
  const response = await fetch(apiUrl("/saved-voices"));
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Failed to load saved voices");
  setSavedVoiceOptions(payload.items || []);
}

voiceFileInput.addEventListener("change", () => {
  const file = voiceFileInput.files && voiceFileInput.files[0];
  if (!file) return;
  const lower = file.name.toLowerCase();
  if (!lower.endsWith(".wav") && !lower.endsWith(".mp3") && !lower.endsWith(".m4a")) {
    statusEl.textContent = "Please choose a .wav, .mp3, or .m4a file.";
    voiceFileInput.value = "";
    return;
  }
  voiceForSubmit = { blob: file, filename: file.name };
  if (uploadObjectUrl) URL.revokeObjectURL(uploadObjectUrl);
  uploadObjectUrl = URL.createObjectURL(file);
  uploadPlayback.src = uploadObjectUrl;
  uploadPlayback.classList.remove("hidden");
  recordingPlayback.classList.add("hidden");
  statusEl.textContent = `Using uploaded file: ${file.name}`;
});

recordButton.addEventListener("click", async () => {
  try {
    const stream = await getMicStream();
    chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (event) => chunks.push(event.data);
    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      voiceForSubmit = { blob, filename: "recording.webm" };
      voiceFileInput.value = "";
      if (uploadObjectUrl) {
        URL.revokeObjectURL(uploadObjectUrl);
        uploadObjectUrl = null;
      }
      uploadPlayback.classList.add("hidden");
      recordingPlayback.src = URL.createObjectURL(blob);
      recordingPlayback.classList.remove("hidden");
      stream.getTracks().forEach((track) => track.stop());
      statusEl.textContent = "Recording ready. Enter text and generate.";
    };
    recorder.start();
    recordButton.disabled = true;
    stopButton.disabled = false;
    statusEl.textContent = "Recording...";
  } catch (error) {
    statusEl.textContent = `Microphone access failed: ${error.message}`;
  }
});

stopButton.addEventListener("click", () => {
  if (recorder && recorder.state !== "inactive") recorder.stop();
  recordButton.disabled = false;
  stopButton.disabled = true;
});

saveCurrentVoiceBtn.addEventListener("click", async () => {
  if (!voiceForSubmit) {
    statusEl.textContent = "Upload a sample first, then save it.";
    return;
  }
  const name = (saveVoiceName.value || "").trim();
  if (!name) {
    statusEl.textContent = "Enter a name for the saved voice.";
    return;
  }
  const data = new FormData();
  data.append("name", name);
  data.append("voice", voiceForSubmit.blob, voiceForSubmit.filename);
  const response = await fetch(apiUrl("/saved-voices"), { method: "POST", body: data });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Failed to save voice");
  statusEl.textContent = `Saved voice: ${payload.name}`;
  await loadSavedVoices();
  if (payload.id) savedVoiceSelect.value = payload.id;
  saveVoiceName.value = "";
});

refreshSavedVoicesBtn.addEventListener("click", async () => {
  await loadSavedVoices();
  statusEl.textContent = "Saved voices refreshed.";
});

deleteSavedVoiceBtn.addEventListener("click", async () => {
  const voiceId = savedVoiceSelect.value;
  if (!voiceId) {
    statusEl.textContent = "Select a saved voice to delete.";
    return;
  }
  const response = await fetch(apiUrl(`/saved-voices/${encodeURIComponent(voiceId)}`), { method: "DELETE" });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Failed to delete saved voice");
  statusEl.textContent = "Deleted saved voice.";
  await loadSavedVoices();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  stopGeneratePolling();
  const savedVoiceId = savedVoiceSelect.value;
  if (!voiceForSubmit && !savedVoiceId) {
    statusEl.textContent = "Upload a voice or select a saved voice first.";
    return;
  }

  const data = new FormData();
  data.append("text", textInput.value);
  data.append("source_language", sourceLanguage.value);
  data.append("target_language", targetLanguage.value);
  data.append("language_flow", `${sourceLanguage.value}-${targetLanguage.value}`);
  if (skipTranslation.checked) data.append("skip_translation", "1");
  if (voiceForSubmit) data.append("voice", voiceForSubmit.blob, voiceForSubmit.filename);
  else data.append("saved_voice_id", savedVoiceId);
  const refEl = document.getElementById("refText");
  if (refEl.value.trim()) data.append("ref_text", refEl.value.trim());
  if (document.getElementById("autoTranscribe").checked) {
    data.append("auto_transcribe", "1");
    data.append("asr_model", document.getElementById("asrModel").value);
  }

  result.classList.add("hidden");
  statusEl.textContent = "Queued for generation...";

  const response = await fetch(apiUrl("/generate"), { method: "POST", body: data });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Generation failed");

  const pollStatus = async () => {
    const statusResponse = await fetch(apiUrl(`/generate-status/${encodeURIComponent(payload.job_id)}`));
    const statusPayload = await statusResponse.json();
    if (!statusResponse.ok) throw new Error(statusPayload.error || "Failed to load status");
    if (statusPayload.status_message) statusEl.textContent = statusPayload.status_message;
    if (statusPayload.status === "done") {
      stopGeneratePolling();
      targetLanguageLabel.textContent = `${statusPayload.target_language_name || "Generated"}:`;
      generatedText.textContent = statusPayload.target_text || "";
      voicePlayback.src = `${apiUrl(statusPayload.audio_url)}?t=${Date.now()}`;
      result.classList.remove("hidden");
    } else if (statusPayload.status === "error") {
      stopGeneratePolling();
      throw new Error(statusPayload.error || "Generation failed");
    }
  };

  await pollStatus();
  if (!activeGeneratePoll) activeGeneratePoll = setInterval(pollStatus, 1000);
});

sourceLanguage.addEventListener("change", updateLanguageSelectors);
targetLanguage.addEventListener("change", updateLanguageSelectors);
skipTranslation.addEventListener("change", updateLanguageHintAndInputText);

async function bootstrap() {
  try {
    await resolveBackendBaseUrl();
    await loadSavedVoices();
    updateLanguageSelectors();
    statusEl.textContent = "Ready.";
  } catch (error) {
    statusEl.textContent = error.message;
  }
}

bootstrap();
