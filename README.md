# Voice German Cloner

Type English text, translate it to German, then speak the German text using your voice from a reference audio sample.

## Important consent note
Only clone voices you own or have explicit permission to use.

## Project layout

- `voice_samples/` — put your reference voice recording here, e.g. `my_voice.wav`
- `outputs/` — generated German speech files go here
- `src/voice_german_cloner/` — app code

## Recommended reference audio

Use a clean WAV/MP3 recording of your voice:
- 10–30 seconds is enough for XTTS-style cloning
- no background music/noise
- only your voice
- normal speaking voice

## Setup (uv)

[uv](https://docs.astral.sh/uv/) manages the virtualenv and installs this package from `pyproject.toml` (with `src/` on the path). The repo includes a `uv.lock` for reproducible installs.

```bash
cd ~/voice-german-cloner
uv sync
```

Optional dev tools (e.g. pytest):

```bash
uv sync --extra dev
```

`TTS` requires Python `<3.12`. A `.python-version` file pins **3.11** for uv; override with e.g. `uv python pin 3.10` if you prefer 3.10.

### Without uv

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r requirements.txt
```

(`pip install -e .` is required so `python -m voice_german_cloner` resolves the package from `src/`.)


## Web interface

```bash
uv run python -m voice_german_cloner.web
```

Or the script entry point:

```bash
uv run voice-german-web
```

The server binds to **all interfaces** (`0.0.0.0:7860`). On this machine open [http://127.0.0.1:7860](http://127.0.0.1:7860); from another device on your LAN use `http://<this-hosts-ip>:7860`.

The web page lets you:
- record your voice in the browser
- play back the recording
- enter English text
- translate it to German
- generate and play the German audio in your recorded voice

Note: microphone access from the browser usually requires `localhost` / `127.0.0.1` or **HTTPS**. If you open the app by raw IP or hostname, the browser may refuse the mic unless you terminate TLS in front of the app or use a secure context.

## Command-line mode

```bash
uv run python -m voice_german_cloner --text "Good morning, how are you?" --speaker voice_samples/my_voice.wav --out outputs/german_voice.wav
```

Or interactive mode:

```bash
uv run python -m voice_german_cloner --speaker voice_samples/my_voice.wav
```

(`uv run voice-german-cloner ...` works the same as `uv run python -m voice_german_cloner ...`.)

## Notes

This scaffold uses:
- `deep-translator` for English → German translation using Google Translate
- Coqui `TTS` with XTTS v2 for multilingual voice cloning

The first run downloads the TTS model and can take a while.
