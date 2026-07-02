# Transcriber MVP

Small CLI for transcribing audio/video files and keeping completed artifacts under
`source/completed`.

By default it uses a local Whisper command and does not need an OpenAI API key.
Pass `--ai` to use OpenAI speech-to-text instead.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Edit `.env` for default settings such as the source directory, language, local
Whisper model, and optional OpenAI API key. Command-line flags override `.env`
values.

Default local transcription expects the `whisper` command to be available on
`PATH`. OpenAI transcription also needs:

```bash
export OPENAI_API_KEY="your-api-key"
```

For `--ai`, `ffmpeg` is used automatically when a file is larger than the upload
limit, so long meeting recordings are split into speech-friendly audio chunks
before transcription.

## Usage

Transcribe one file by path:

```bash
python main.py "Weekly QUT Meeting.m4a" --source-dir source --language en
```

Transcribe every supported media file directly inside `source`:

```bash
python main.py --source-dir source --language en
```

Add meeting-specific context when names or acronyms matter:

```bash
python main.py "Weekly QUT Meeting.m4a" \
  --source-dir source \
  --language en \
  --prompt "This is a weekly QUT meeting. Preserve names, acronyms, decisions, and action items."
```

Use OpenAI instead of local Whisper:

```bash
python main.py "Weekly QUT Meeting.m4a" --source-dir source --language en --ai
```

Use OpenAI speaker labels:

```bash
python main.py "Weekly QUT Meeting.m4a" --source-dir source --language en --ai --diarize
```

## Output Rules

- If the file is inside `source`, it is moved only after transcription succeeds.
- Each run writes to `source/completed/<original file name without extension>/`.
- A local source file is moved to that job directory beside the transcript artifacts.
- If the file path points outside `source`, the original file stays where it is and
  the completed directory receives the transcript plus a `report.json` record.
- If transcription fails, a `report.json` failure record is still written and the
  original file is not moved.

Artifacts:

- `transcript.txt` - human-readable transcript
- `transcript.json` - raw model response details
- `report.json` - source location, model, status, movement decision, and errors

Supported input extensions: `flac`, `m4a`, `mp3`, `mp4`, `mpeg`, `mpga`, `ogg`,
`wav`, and `webm`.
