from __future__ import annotations

import argparse
import os
from pathlib import Path

from transcriber_mvp.ai_help import (
    DEFAULT_AI_HELP_CHUNK_CHARS,
    DEFAULT_AI_HELP_MODEL,
    AIHelpConfig,
    run_ai_help_for_path,
)
from transcriber_mvp.env import env_bool, env_float, load_env_file
from transcriber_mvp.progress import BLUE, BOLD, GREEN, RED, YELLOW, color
from transcriber_mvp.workflow import (
    DEFAULT_CHUNK_SECONDS,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_MAX_UPLOAD_BYTES,
    DEFAULT_MODEL,
    JobConfig,
    run_jobs,
)


def _env_known_speakers() -> list[str]:
    value = os.getenv("TRANSCRIBER_KNOWN_SPEAKERS", "")
    return [item.strip() for item in value.split(",") if item.strip()]


def build_parser() -> argparse.ArgumentParser:
    load_env_file()

    parser = argparse.ArgumentParser(
        description="Transcribe audio/video files and write completed artifacts."
    )
    parser.add_argument(
        "media",
        nargs="?",
        help=(
            "Optional audio/video file path. If omitted, supported media files in "
            "the source directory are processed."
        ),
    )
    parser.add_argument(
        "--source-dir",
        default=os.getenv("TRANSCRIBER_SOURCE_DIR", "source"),
        help="Directory to scan for source files and where completed artifacts live.",
    )
    parser.add_argument(
        "--ai",
        action=argparse.BooleanOptionalAction,
        default=env_bool("TRANSCRIBER_USE_AI", False),
        help="Use the OpenAI API backend. The default uses local Whisper.",
    )
    parser.add_argument(
        "--=ai",
        dest="ai",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--model",
        default=os.getenv("TRANSCRIBER_OPENAI_MODEL", DEFAULT_MODEL),
        help="OpenAI transcription model to use with --ai.",
    )
    parser.add_argument(
        "--local-model",
        default=os.getenv("TRANSCRIBER_LOCAL_MODEL", DEFAULT_LOCAL_MODEL),
        help="Local Whisper model to use when --ai is not set.",
    )
    parser.add_argument(
        "--local-device",
        default=os.getenv("TRANSCRIBER_LOCAL_DEVICE") or None,
        help="Optional local Whisper device, such as cpu or cuda.",
    )
    parser.add_argument(
        "--language",
        default=os.getenv("TRANSCRIBER_LANGUAGE") or None,
        help="Optional language hint, such as en.",
    )
    parser.add_argument(
        "--prompt",
        default=os.getenv("TRANSCRIBER_PROMPT") or None,
        help="Optional context prompt to improve names, acronyms, and punctuation.",
    )
    parser.add_argument(
        "--diarize",
        action="store_true",
        default=env_bool("TRANSCRIBER_DIARIZE", False),
        help="Use OpenAI speaker diarization. Requires --ai.",
    )
    parser.add_argument(
        "--speaker-labels",
        default=os.getenv("TRANSCRIBER_SPEAKER_LABELS") or None,
        help="Rename diarized labels, for example A=Pedro,B=Supervisor. Requires --ai --diarize.",
    )
    parser.add_argument(
        "--known-speaker",
        action="append",
        default=_env_known_speakers(),
        help="Known speaker sample as Name=/path/audio.wav. Repeat up to 4 times. Requires --ai --diarize.",
    )
    parser.add_argument(
        "--chunk-minutes",
        type=float,
        default=env_float("TRANSCRIBER_CHUNK_MINUTES", DEFAULT_CHUNK_SECONDS / 60),
        help="Chunk length used when a media file is too large to upload directly.",
    )
    parser.add_argument(
        "--max-upload-mb",
        type=float,
        default=env_float(
            "TRANSCRIBER_MAX_UPLOAD_MB",
            DEFAULT_MAX_UPLOAD_BYTES / 1024 / 1024,
        ),
        help="Maximum upload size per transcription request.",
    )
    parser.add_argument(
        "--ai-help",
        action="store_true",
        default=env_bool("TRANSCRIBER_AI_HELP", False),
        help="Run OpenAI cleanup, summary, and action-item extraction after transcription.",
    )
    parser.add_argument(
        "--ai-help-only",
        help="Run AI help on an existing transcript.txt or completed job folder and exit.",
    )
    parser.add_argument(
        "--ai-help-model",
        default=os.getenv("TRANSCRIBER_AI_HELP_MODEL", DEFAULT_AI_HELP_MODEL),
        help="OpenAI text model for AI help. Use 'auto' to select an available model.",
    )
    parser.add_argument(
        "--ai-help-chunk-chars",
        type=int,
        default=int(
            env_float("TRANSCRIBER_AI_HELP_CHUNK_CHARS", DEFAULT_AI_HELP_CHUNK_CHARS)
        ),
        help="Character chunk size for AI cleanup of long transcripts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.diarize and not args.ai:
        parser.error("--diarize requires --ai because local Whisper has no speaker labels")
    if (args.speaker_labels or args.known_speaker) and not (args.ai and args.diarize):
        parser.error("--speaker-labels and --known-speaker require --ai --diarize")
    if len(args.known_speaker) > 4:
        parser.error("--known-speaker supports up to 4 speaker reference files")

    ai_help_config = AIHelpConfig(
        model=args.ai_help_model,
        chunk_chars=args.ai_help_chunk_chars,
    )
    if args.ai_help_only:
        try:
            ai_result = run_ai_help_for_path(Path(args.ai_help_only), ai_help_config)
            _print_ai_help_report(ai_result)
            return 0
        except Exception as exc:
            print(color("AI help failed", RED))
            print(f"  Error: {exc}")
            return 1

    config = JobConfig(
        source_dir=Path(args.source_dir),
        media_arg=args.media,
        use_ai=args.ai,
        model=args.model,
        local_model=args.local_model,
        local_device=args.local_device,
        language=args.language,
        prompt=args.prompt,
        diarize=args.diarize,
        speaker_labels=args.speaker_labels,
        known_speakers=tuple(args.known_speaker),
        chunk_seconds=max(60, int(args.chunk_minutes * 60)),
        max_upload_bytes=max(1_000_000, int(args.max_upload_mb * 1024 * 1024)),
    )

    results = run_jobs(config)
    if not results:
        print(f"No supported audio/video files found in {config.source_dir}")
        return 1

    exit_code = 0
    print()
    for result in results:
        _print_result_report(result)
        if result.error:
            exit_code = 1
            continue
        if args.ai_help:
            try:
                ai_result = run_ai_help_for_path(result.output_dir, ai_help_config)
                _print_ai_help_report(ai_result)
            except Exception as exc:
                print(color("AI help failed", RED))
                print(f"  Error: {exc}")
                exit_code = 1
    return exit_code


def _print_result_report(result) -> None:
    if result.status == "completed":
        status = color("COMPLETED", GREEN)
    else:
        status = color("FAILED", RED)

    print(color("Transcription Report", BOLD))
    print(f"  Status: {status}")
    print(f"  Source: {result.source_path}")
    print(f"  Output folder: {color(str(result.output_dir), BLUE)}")

    transcript_path = result.output_dir / "transcript.txt"
    report_path = result.output_dir / "report.json"
    if result.status == "completed":
        print(f"  Transcript: {color(str(transcript_path), GREEN)}")
        print(f"  Report: {report_path}")
        print(f"  Source moved: {'yes' if result.moved_source else 'no'}")
    else:
        print(f"  Report: {color(str(report_path), YELLOW)}")
        if result.error:
            print(f"  Error: {result.error}")
    print()


def _print_ai_help_report(result) -> None:
    print(color("AI Help Report", BOLD))
    print(f"  Status: {color('COMPLETED', GREEN)}")
    print(f"  Model: {result.model}")
    print(f"  Source transcript: {result.transcript_path}")
    print(f"  Output folder: {color(str(result.output_dir), BLUE)}")
    print(f"  Cleaned transcript: {color(str(result.cleaned_transcript_path), GREEN)}")
    print(f"  Summary: {color(str(result.summary_path), GREEN)}")
    print(f"  Action items: {color(str(result.action_items_path), GREEN)}")
    print(f"  Report: {result.report_path}")
    print()
