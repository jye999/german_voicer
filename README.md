# Multilingual Voice Cloner

Translate selected language pairs locally, or enter target-language text directly, then speak the result with **[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)** **Base** voice cloning from a short reference clip.

## Important consent note

Only clone voices you **own** or have **explicit permission** to use.

## How it works

- **Text input** — choose one of the supported local Marian flows, or a direct same-language flow that skips translation.
- **Speech** — `Qwen3TTSModel` **Base** (`generate_voice_clone`) with the selected target language and your file as `ref_audio`.

### Supported language flows

These flows are intentionally limited to pairs with explicit local Marian checkpoints and target languages that are a good fit for multilingual Qwen3-TTS usage:

| Flow | Translation model |
|------|-------------------|
| English -> German | `Helsinki-NLP/opus-mt-en-de` |
| German direct | none |
| English -> Chinese | `Helsinki-NLP/opus-mt-en-zh` |
| Chinese direct | none |
| Spanish -> English | `Helsinki-NLP/opus-mt-es-en` |
| English direct | none |
| English -> Spanish | `Helsinki-NLP/opus-mt-en-es` |
| Spanish direct | none |
| German -> English | `Helsinki-NLP/opus-mt-de-en` |
| Chinese -> English | `Helsinki-NLP/opus-mt-zh-en` |

### Cloning modes

| Mode | When | Qwen settings |
|------|------|----------------|
| **Embedding-only** (default) | No transcript and auto-transcribe off | `x_vector_only_mode=True` (no `ref_text`; timbre from audio only) |
| **ICL (stronger match)** | You paste the **exact words** you said in the reference clip, **or** you enable **auto-transcribe** | `ref_text` set, `x_vector_only_mode=False` |

If both a manual transcript and auto-transcribe are sent, the **manual transcript wins** (Whisper is not run).

**Auto-transcribe** runs **OpenAI Whisper** locally (`openai/whisper-tiny` by default). Override with **`WHISPER_ASR_MODEL`**. Best when the reference is **English** (e.g. the suggested script on the web page). Other languages may be wrong without a different Whisper model.

Default TTS checkpoint: **`Qwen/Qwen3-TTS-12Hz-0.6B-Base`**. Override with **`QWEN3_TTS_MODEL`**.

Licensing: follow **Apache-2.0** for the [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) code and the **model license** on Hugging Face for the weights you use.

## Project layout

- `voice_samples/` — reference uploads from the web UI
- `outputs/` — generated speech
- `src/voice_german_cloner/` — application code (`ref_audio_transcribe.py` = Whisper helper)

## Reference audio

Use a clean **WAV / MP3 / M4A** clip, about **10–30 seconds**, solo voice, minimal noise. For ICL, the transcript should match that clip. **ffmpeg** may help `librosa` decode some formats if decoding fails.

## Setup (uv)

```bash
cd ~/german_voicer
uv sync
```

Install system audio tools (Ubuntu/WSL):

```bash
sudo apt update && sudo apt install -y sox ffmpeg
```

Dev (pytest):

```bash
uv sync --extra dev
```

This project pins **Python 3.10–3.11** (see `.python-version`).

### GPU

Qwen3-TTS is intended for **CUDA**; CPU is slow. The app uses **`sdpa`** attention (no FlashAttention build required). Prefer the default **0.6B Base** model if VRAM is tight.

## Web interface

```bash
uv run python -m voice_german_cloner.web
```

Or:

```bash
uv run voice-german-web
```

Bind: `0.0.0.0:7860` — open [http://127.0.0.1:7860](http://127.0.0.1:7860). A **voice sample is required** for first use. In section 3, choose **Source language** and **Target voice language** to translate or speak directly. Optional **reference transcript** field and **Auto-transcribe** checkbox are in section 2 of the form.
When Auto-transcribe is enabled in the web UI, you can choose Whisper `tiny`, `base`, or `small` in a dropdown (default is `tiny`).

The web UI now includes a **Saved voices** section:

- Save an uploaded/recorded sample with a name.
- Reuse that saved voice in later generations without re-uploading.
- Delete saved voices you no longer need.

## Command-line mode

English -> German, embedding-only (default):

```bash
uv run python -m voice_german_cloner --text "Good morning, how are you?" --speaker voice_samples/my_voice.wav --out outputs/german_voice.wav
```

With transcript (ICL):

```bash
uv run python -m voice_german_cloner --text "Good morning" --speaker voice_samples/my_voice.wav --out out.wav \
  --ref-text "Exact words spoken in my_voice.wav"
```

Speak German text directly without translation:

```bash
uv run python -m voice_german_cloner --text "Guten Morgen, wie geht es dir?" --language-flow de-de \
  --speaker voice_samples/my_voice.wav --out outputs/german_voice.wav
```

English -> Chinese:

```bash
uv run python -m voice_german_cloner --text "Good morning" --language-flow en-zh \
  --speaker voice_samples/my_voice.wav --out outputs/chinese_voice.wav
```

Spanish -> English:

```bash
uv run python -m voice_german_cloner --text "Buenos dias" --language-flow es-en \
  --speaker voice_samples/my_voice.wav --out outputs/english_voice.wav
```

Whisper auto-transcribe (ICL, English reference):

```bash
uv run python -m voice_german_cloner --text "Good morning" --speaker voice_samples/my_voice.wav --out out.wav \
  --auto-transcribe-reference
```

Interactive mode supports env overrides:

- **`VOICER_REF_TEXT`** — fixed transcript for every line (ICL).
- **`VOICER_AUTO_TRANSCRIBE=1`** — run Whisper on each generation (slow on CPU).

## Upstream

Track [Qwen3-TTS releases](https://github.com/QwenLM/Qwen3-TTS); `qwen-tts` pins `transformers` and may need updates over time.
