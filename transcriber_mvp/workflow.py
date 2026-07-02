from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from transcriber_mvp.openai_backend import (
    DEFAULT_CHUNK_SECONDS,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_MAX_UPLOAD_BYTES,
    DEFAULT_MODEL,
    TranscriptionConfig,
    TranscriptionPayload,
    transcribe_media,
)
from transcriber_mvp.local_backend import transcribe_media_local


SUPPORTED_EXTENSIONS = {
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".ogg",
    ".wav",
    ".webm",
}


@dataclass(frozen=True)
class JobConfig:
    source_dir: Path = Path("source")
    media_arg: str | None = None
    use_ai: bool = False
    model: str = DEFAULT_MODEL
    local_model: str = DEFAULT_LOCAL_MODEL
    local_device: str | None = None
    language: str | None = None
    prompt: str | None = None
    diarize: bool = False
    speaker_labels: str | None = None
    known_speakers: tuple[str, ...] = ()
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    chunk_seconds: int = DEFAULT_CHUNK_SECONDS


@dataclass(frozen=True)
class JobResult:
    source_path: Path
    output_dir: Path
    status: str
    moved_source: bool
    error: str | None = None


Transcriber = Callable[[Path, Path, TranscriptionConfig], TranscriptionPayload]


def run_jobs(
    config: JobConfig,
    transcriber: Transcriber | None = None,
) -> list[JobResult]:
    source_dir = config.source_dir.expanduser().resolve()
    completed_dir = source_dir / "completed"
    source_dir.mkdir(parents=True, exist_ok=True)
    completed_dir.mkdir(parents=True, exist_ok=True)

    media_paths = _requested_media_paths(config.media_arg, source_dir)
    if not media_paths:
        return []

    results = []
    selected_transcriber = transcriber or _select_transcriber(config)
    for media_path in media_paths:
        results.append(
            _run_one(media_path, source_dir, completed_dir, config, selected_transcriber)
        )
    return results


def _select_transcriber(config: JobConfig) -> Transcriber:
    if config.use_ai:
        return transcribe_media
    return transcribe_media_local


def _requested_media_paths(media_arg: str | None, source_dir: Path) -> list[Path]:
    if media_arg:
        return [_resolve_media_arg(media_arg, source_dir)]

    completed_dir = source_dir / "completed"
    media_paths = []
    for child in sorted(source_dir.iterdir()):
        if child.is_file() and _is_supported_media(child):
            media_paths.append(child.resolve())
        elif child.is_dir() and child.resolve() == completed_dir.resolve():
            continue
    return media_paths


def _resolve_media_arg(media_arg: str, source_dir: Path) -> Path:
    given_path = Path(media_arg).expanduser()
    if given_path.is_absolute():
        return given_path.resolve()

    cwd_candidate = (Path.cwd() / given_path).resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    source_candidate = (source_dir / given_path).resolve()
    if source_candidate.exists():
        return source_candidate

    return cwd_candidate


def _run_one(
    media_path: Path,
    source_dir: Path,
    completed_dir: Path,
    config: JobConfig,
    transcriber: Transcriber,
) -> JobResult:
    output_dir = _unique_output_dir(completed_dir, media_path.stem or "transcription")
    output_dir.mkdir(parents=True, exist_ok=False)

    report = _base_report(media_path, source_dir, output_dir, config)
    moved_source = False
    final_source_path: Path | None = None

    try:
        if not media_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {media_path}")
        if not media_path.is_file():
            raise ValueError(f"Input path is not a file: {media_path}")
        if not _is_supported_media(media_path):
            raise ValueError(
                f"Unsupported media extension: {media_path.suffix}. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        transcription_config = TranscriptionConfig(
            backend="openai" if config.use_ai else "local",
            model=config.model,
            local_model=config.local_model,
            local_device=config.local_device,
            language=config.language,
            prompt=config.prompt,
            diarize=config.diarize,
            speaker_labels=config.speaker_labels,
            known_speakers=config.known_speakers,
            max_upload_bytes=config.max_upload_bytes,
            chunk_seconds=config.chunk_seconds,
        )
        payload = transcriber(media_path, output_dir, transcription_config)
        _write_text(output_dir / "transcript.txt", payload.text)
        _write_json(output_dir / "transcript.json", payload.raw)

        should_move = _is_under(media_path, source_dir) and not _is_under(
            media_path, completed_dir
        )
        if should_move:
            final_source_path = output_dir / media_path.name
            shutil.move(str(media_path), str(final_source_path))
            moved_source = True
        else:
            final_source_path = media_path

        report.update(
            {
                "status": "completed",
                "completed_at": _now_iso(),
                "source_was_moved": moved_source,
                "final_source_path": str(final_source_path),
                "transcript_path": str(output_dir / "transcript.txt"),
                "transcript_json_path": str(output_dir / "transcript.json"),
            }
        )
        _write_json(output_dir / "report.json", report)
        return JobResult(media_path, output_dir, "completed", moved_source)
    except Exception as exc:
        report.update(
            {
                "status": "failed",
                "completed_at": _now_iso(),
                "source_was_moved": moved_source,
                "final_source_path": str(final_source_path) if final_source_path else None,
                "error": str(exc),
            }
        )
        _write_json(output_dir / "report.json", report)
        return JobResult(media_path, output_dir, "failed", moved_source, str(exc))


def _base_report(
    media_path: Path,
    source_dir: Path,
    output_dir: Path,
    config: JobConfig,
) -> dict[str, object]:
    file_size = media_path.stat().st_size if media_path.exists() and media_path.is_file() else None
    completed_dir = source_dir / "completed"
    return {
        "created_at": _now_iso(),
        "source_path": str(media_path),
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "file_name": media_path.name,
        "file_stem": media_path.stem,
        "file_size_bytes": file_size,
        "input_was_inside_source_dir": _is_under(media_path, source_dir)
        and not _is_under(media_path, completed_dir),
        "backend": "openai" if config.use_ai else "local",
        "model": config.model,
        "local_model": config.local_model,
        "local_device": config.local_device,
        "diarize": config.diarize,
        "speaker_labels": config.speaker_labels,
        "known_speaker_count": len(config.known_speakers),
        "language": config.language,
        "prompt_provided": bool(config.prompt),
        "chunk_seconds": config.chunk_seconds,
        "max_upload_bytes": config.max_upload_bytes,
    }


def _unique_output_dir(completed_dir: Path, preferred_name: str) -> Path:
    safe_name = _safe_dir_name(preferred_name)
    candidate = completed_dir / safe_name
    if not candidate.exists():
        return candidate

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for counter in range(1, 1000):
        candidate = completed_dir / f"{safe_name}-{timestamp}-{counter:03d}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("Could not create a unique completed output directory.")


def _safe_dir_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return cleaned or "transcription"


def _is_supported_media(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def _is_under(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def _write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_config_to_dict(config: JobConfig) -> dict[str, object]:
    data = asdict(config)
    data["source_dir"] = str(config.source_dir)
    return data
