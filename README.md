# SourceScribe

Small CLI for transcribing audio/video files and keeping completed artifacts under
`source/completed`.

By default it uses a local Whisper command and does not need an OpenAI API key.
Pass `--ai` to use OpenAI speech-to-text instead.

Project planning and follow-up work live in [TODO.md](TODO.md). Keep README and
TODO updated whenever the code changes.

## Setup

Run the one-command setup first:

```bash
./start
```

It creates the virtual environment, installs Python dependencies, creates `.env`
when needed, checks `ffmpeg`, verifies local Whisper, and prepares the configured
local Whisper model with a tiny generated audio file. It does not transcribe or
move source files.

During setup it asks whether you want to paste an OpenAI API key. Answering yes
saves it to `.env`; OpenAI is still only used when you run with `--ai`.

Manual setup is:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Edit `.env` for default settings such as the source directory, language, local
Whisper model, and optional OpenAI API key. Command-line flags override `.env`
values.

Default local transcription expects the `whisper` command to be available on
`PATH`. CPU/default local Whisper runs pass `--fp16 False` to avoid the expected
half-precision warning. OpenAI transcription also needs:

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

The command shows progress while transcription runs when the backend can report
it. At completion it prints a short report with the output folder, transcript
path, report path, and whether the original source file was moved.

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

With diarization, the transcript is written with a speaker label before each
sentence:

```text
[00:00:01 - 00:00:04] Speaker A: Hello there.
[00:00:05 - 00:00:06] Speaker B: Good thanks.
```

Rename model labels when you know who they are:

```bash
python main.py "Weekly QUT Meeting.m4a" \
  --source-dir source \
  --language en \
  --ai \
  --diarize \
  --speaker-labels "A=Pedro,B=Supervisor"
```

Provide reference samples when you have short audio clips of known speakers:

```bash
python main.py "Weekly QUT Meeting.m4a" \
  --source-dir source \
  --language en \
  --ai \
  --diarize \
  --known-speaker "Pedro=/path/pedro-sample.wav" \
  --known-speaker "Supervisor=/path/supervisor-sample.wav"
```

Without `--speaker-labels` or `--known-speaker`, OpenAI can separate speakers but
will normally name them `Speaker A`, `Speaker B`, and so on.

To rerun OpenAI diarization on a media file that was already moved into a
completed job folder:

```bash
python main.py \
  "source/completed/Weekly QUT Meeting-20260702-142719-001/Weekly QUT Meeting.m4a" \
  --source-dir source \
  --language en \
  --ai \
  --diarize \
  --speaker-labels "A=Pedro,B=Supervisor"
```

Run OpenAI AI-help after a transcription:

```bash
python main.py --source-dir source --language en --ai-help
```

Run AI-help on an existing completed job or `transcript.txt`:

```bash
python main.py --ai-help-only "source/completed/Weekly QUT Meeting-20260702-142719-001"
```

AI-help writes separate artifacts under `ai_help/` and does not overwrite the raw
transcript. The OpenAI key must have available API quota/billing for this step.

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
- `ai_help/transcript_ai_cleaned.md` - OpenAI-cleaned transcript when requested
- `ai_help/meeting_summary.md` - OpenAI-generated meeting summary when requested
- `ai_help/action_items.md` - OpenAI-extracted action items when requested

Supported input extensions: `flac`, `m4a`, `mp3`, `mp4`, `mpeg`, `mpga`, `ogg`,
`wav`, and `webm`.
