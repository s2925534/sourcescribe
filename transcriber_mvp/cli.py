from __future__ import annotations

import argparse
import os
from pathlib import Path

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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.diarize and not args.ai:
        parser.error("--diarize requires --ai because local Whisper has no speaker labels")

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
