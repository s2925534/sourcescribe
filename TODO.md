# SourceScribe TODO

Keep this file updated alongside `README.md` whenever code or project behavior
changes.

## Current Status

- [x] Create CLI entrypoint with `main.py`.
- [x] Scan `source/` for supported media files when no explicit path is given.
- [x] Support explicit audio/video file paths.
- [x] Move source files into `source/completed/<file stem>/` after successful transcription.
- [x] Leave external input files in place and write a completion report.
- [x] Write `transcript.txt`, `transcript.json`, and `report.json`.
- [x] Use local Whisper by default.
- [x] Add optional OpenAI API backend with `--ai`.
- [x] Support `--diarize` for OpenAI speaker labels.
- [x] Add `.env.example` and local `.env` defaults.
- [x] Add `./start` setup script.
- [x] Prompt for optional OpenAI API key during setup.
- [x] Apply certificate bundle handling for local Whisper downloads.
- [x] Add progress output and completion report in the terminal.
- [x] Add workflow and progress tests.
- [x] Complete the first full local transcript for `Weekly QUT Meeting.m4a`.
- [x] Suppress the local Whisper CPU FP16 warning by passing `--fp16 False`.
- [x] Add OpenAI AI-help for existing transcripts and post-transcription cleanup.
- [x] Format OpenAI diarized transcripts with speaker labels before each sentence.
- [x] Add manual speaker label mapping and known-speaker reference options.

## Next

- [ ] Review the first transcript quality and decide whether `turbo` is good enough.
- [ ] Decide whether OpenAI should be used for high-quality final transcripts.
- [ ] Run AI-help on the first completed transcript and review the artifacts.
- [ ] Confirm OpenAI project billing/quota before running AI-help on full transcripts.
- [ ] Run an OpenAI diarized transcript once API quota is available.
- [ ] Add a `--cleanup-failed` or `--overwrite` option for failed completed folders.
- [ ] Improve setup output by reducing noisy `pip` lines unless there is an error.

## Backlog

- [ ] Add optional Markdown transcript output.
- [ ] Add optional SRT/VTT subtitle output from local Whisper.
- [ ] Add richer metadata in `report.json`, including duration and backend runtime.
- [ ] Add a dry-run mode that shows which files would be processed.
- [ ] Add support for processing nested source folders.
- [ ] Add resumable processing for interrupted long transcriptions.
- [ ] Add better local model setup options: `tiny`, `base`, `small`, `medium`, `turbo`.
- [ ] Add CI checks for tests and linting after the repo is published.
