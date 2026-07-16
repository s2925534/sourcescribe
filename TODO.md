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
- [x] Complete the first full local transcript run.
- [x] Suppress the local Whisper CPU FP16 warning by passing `--fp16 False`.
- [x] Add OpenAI AI-help for existing transcripts and post-transcription cleanup.
- [x] Format OpenAI diarized transcripts with speaker labels before each sentence.
- [x] Add manual speaker label mapping and known-speaker reference options.
- [x] Document that AI is optional and `--ai` enables high-quality AI mode.
- [x] Add MIT license and author details.

## Next

- [ ] Stabilize the project as an importable Python package with a documented public API.
- [ ] Add `pyproject.toml` package metadata and expose a console script entrypoint such as `sourcescribe`.
- [ ] Review the first transcript quality and decide whether `turbo` is good enough.
- [ ] Decide whether OpenAI should be used for high-quality final transcripts.
- [ ] Run AI-help on the first completed transcript and review the artifacts.
- [ ] Confirm OpenAI project billing/quota before running AI-help on full transcripts.
- [ ] Run an OpenAI diarized transcript once API quota is available.
- [ ] Add a `--cleanup-failed` or `--overwrite` option for failed completed folders.
- [ ] Improve setup output by reducing noisy `pip` lines unless there is an error.
- [ ] Keep platform/SaaS work in the private sibling project at `../sourcescribe-platform`.

## Backlog

- [ ] Add optional Markdown transcript output.
- [ ] Add optional SRT/VTT subtitle output from local Whisper.
- [ ] Add richer metadata in `report.json`, including duration and backend runtime.
- [ ] Add a dry-run mode that shows which files would be processed.
- [ ] Add support for processing nested source folders.
- [ ] Add resumable processing for interrupted long transcriptions.
- [ ] Add better local model setup options: `tiny`, `base`, `small`, `medium`, `turbo`.
- [ ] Add CI checks for tests and linting after the repo is published.

## Package Stabilization

The project should work in two modes:

1. As a standalone CLI tool for local use.
2. As an importable Python package that other projects can call safely.

- [ ] Rename or alias the package to a stable distribution name, such as `sourcescribe`.
- [ ] Add `pyproject.toml` with project metadata, dependencies, Python version support, license, authors, and console scripts.
- [ ] Keep `main.py` as a compatibility wrapper, but make the packaged CLI entrypoint the primary command.
- [ ] Define a small public API in `transcriber_mvp/__init__.py` or a renamed package module.
- [ ] Document public functions for running one job, running many jobs, running AI-help, and reading generated artifacts.
- [ ] Add stable dataclasses or typed result objects for job configuration, progress updates, job results, and artifact paths.
- [ ] Add a progress callback interface so external apps can receive structured progress instead of scraping terminal output.
- [ ] Separate terminal printing from core workflow logic so imports do not produce unwanted console output.
- [ ] Add package-level exceptions for expected failures, such as missing media, unsupported format, missing backend dependency, OpenAI quota failure, and transcription failure.
- [ ] Add semantic versioning and a `CHANGELOG.md`.
- [ ] Add package build checks with `python -m build`.
- [ ] Add installation docs for editable installs, direct Git installs, and packaged installs.
- [ ] Add tests that import the package exactly as downstream projects would.
- [ ] Add GitHub Actions or another CI workflow for tests, package build, and lint/type checks.
- [ ] Add a minimal API usage example that does not rely on CLI arguments.

## Platform Boundary

The CLI should remain a small standalone transcription tool. Multi-user SaaS
features belong in the private platform project and should consume this project
as a package or subprocess-level transcription engine.

- [ ] Keep this repo focused on CLI usability, transcription quality, output formats, and engine reliability.
- [ ] Avoid adding user accounts, billing, dashboards, web uploads, or SaaS administration here.
- [ ] Expose stable Python interfaces that the platform can call without depending on CLI-only behavior.
- [ ] Consider publishing/tagging this repo privately or publicly so the platform can pin a version.
