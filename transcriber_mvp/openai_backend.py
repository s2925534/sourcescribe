from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transcriber_mvp.progress import print_progress


DEFAULT_MODEL = "gpt-4o-transcribe"
DIARIZATION_MODEL = "gpt-4o-transcribe-diarize"
DEFAULT_MAX_UPLOAD_BYTES = 24 * 1024 * 1024
DEFAULT_CHUNK_SECONDS = 20 * 60
DEFAULT_LOCAL_MODEL = "turbo"


@dataclass(frozen=True)
class TranscriptionConfig:
    backend: str = "local"
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
class TranscriptionPayload:
    text: str
    raw: dict[str, Any]
    chunks: list[dict[str, Any]]


def transcribe_media(
    media_path: Path,
    output_dir: Path,
    config: TranscriptionConfig,
) -> TranscriptionPayload:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export it before running transcription."
        )

    upload_paths = _prepare_uploads(media_path, output_dir, config)
    chunk_results: list[dict[str, Any]] = []
    transcript_parts: list[str] = []
    started_at = time.monotonic()

    for index, upload_path in enumerate(upload_paths, start=1):
        print_progress(
            "openai chunks",
            index - 1,
            len(upload_paths),
            started_at,
            stream=sys.stderr,
        )
        prompt = _prompt_for_chunk(config.prompt, transcript_parts)
        response = _call_openai(upload_path, config, prompt)
        response_data = _response_to_dict(response)
        text = _response_to_text(response_data, config).strip()
        chunk_results.append(
            {
                "index": index,
                "path": str(upload_path),
                "text": text,
                "response": response_data,
            }
        )
        if text:
            if len(upload_paths) > 1:
                transcript_parts.append(f"[Part {index}]\n{text}")
            else:
                transcript_parts.append(text)
        print_progress(
            "openai chunks",
            index,
            len(upload_paths),
            started_at,
            stream=sys.stderr,
            done=index == len(upload_paths),
        )

    text = "\n\n".join(transcript_parts).strip()
    raw: dict[str, Any] = {
        "model": _effective_model(config),
        "diarize": config.diarize,
        "speaker_label_map": _parse_speaker_labels(config.speaker_labels),
        "known_speaker_names": [name for name, _ in _parse_known_speakers(config.known_speakers)],
        "chunk_count": len(upload_paths),
        "chunks": chunk_results,
    }
    return TranscriptionPayload(text=text, raw=raw, chunks=chunk_results)


def _prepare_uploads(
    media_path: Path,
    output_dir: Path,
    config: TranscriptionConfig,
) -> list[Path]:
    if media_path.stat().st_size <= config.max_upload_bytes:
        return [media_path]

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError(
            "The media file is larger than the upload limit and ffmpeg/ffprobe "
            "are required for chunking."
        )

    if config.diarize:
        compressed_upload = _prepare_single_speech_upload(media_path, output_dir, config)
        if compressed_upload:
            return [compressed_upload]

    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    chunk_template = chunks_dir / "chunk_%03d.m4a"

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(media_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-f",
        "segment",
        "-segment_time",
        str(config.chunk_seconds),
        "-reset_timestamps",
        "1",
        str(chunk_template),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)

    chunks = sorted(chunks_dir.glob("chunk_*.m4a"))
    if not chunks:
        raise RuntimeError("ffmpeg did not produce any transcription chunks.")

    oversize = [chunk for chunk in chunks if chunk.stat().st_size > config.max_upload_bytes]
    if oversize:
        names = ", ".join(chunk.name for chunk in oversize[:3])
        raise RuntimeError(
            f"Chunking produced files over the upload limit: {names}. "
            "Try a smaller --chunk-minutes value."
        )

    return chunks


def _prepare_single_speech_upload(
    media_path: Path,
    output_dir: Path,
    config: TranscriptionConfig,
) -> Path | None:
    upload_dir = output_dir / "openai_upload"
    upload_dir.mkdir(parents=True, exist_ok=True)

    for bitrate in ("32k", "24k", "16k"):
        candidate = upload_dir / f"diarized_upload_{bitrate}.m4a"
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(media_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "aac",
            "-b:a",
            bitrate,
            str(candidate),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        if candidate.stat().st_size <= config.max_upload_bytes:
            return candidate

    return None


def _call_openai(
    upload_path: Path,
    config: TranscriptionConfig,
    prompt: str | None,
) -> Any:
    from openai import OpenAI

    client = OpenAI()
    model = _effective_model(config)
    reference_files = []
    kwargs: dict[str, Any] = {
        "model": model,
        "file": upload_path.open("rb"),
    }

    try:
        if config.language:
            kwargs["language"] = config.language

        if model == DIARIZATION_MODEL:
            kwargs["response_format"] = "diarized_json"
            kwargs["chunking_strategy"] = "auto"
            known_speakers = _parse_known_speakers(config.known_speakers)
            if known_speakers:
                kwargs["known_speaker_names"] = [name for name, _ in known_speakers]
                reference_files = [path.open("rb") for _, path in known_speakers]
                kwargs["known_speaker_references"] = reference_files
        else:
            kwargs["response_format"] = "json"
            if prompt:
                kwargs["prompt"] = prompt

        return client.audio.transcriptions.create(**kwargs)
    finally:
        kwargs["file"].close()
        for reference_file in reference_files:
            reference_file.close()


def _effective_model(config: TranscriptionConfig) -> str:
    if config.diarize:
        return DIARIZATION_MODEL
    return config.model


def _prompt_for_chunk(base_prompt: str | None, transcript_parts: list[str]) -> str | None:
    pieces = []
    if base_prompt:
        pieces.append(base_prompt.strip())

    if transcript_parts:
        previous_text = "\n\n".join(transcript_parts)
        pieces.append(
            "Continue the same transcript. The previous transcript ended with:\n"
            + previous_text[-1800:]
        )

    return "\n\n".join(piece for piece in pieces if piece)


def _response_to_dict(response: Any) -> dict[str, Any]:
    if hasattr(response, "model_dump"):
        return response.model_dump(mode="json")
    if isinstance(response, dict):
        return response
    if isinstance(response, str):
        return {"text": response}
    try:
        return json.loads(response.model_dump_json())
    except Exception:
        return {"text": str(response)}


def _response_to_text(
    response_data: dict[str, Any],
    config: TranscriptionConfig | None = None,
) -> str:
    segments = response_data.get("segments")
    if isinstance(segments, list) and segments and "speaker" in segments[0]:
        lines = []
        speaker_labels = _parse_speaker_labels(config.speaker_labels if config else None)
        for segment in segments:
            speaker = _speaker_name(segment.get("speaker", "Speaker"), speaker_labels)
            start = _format_time(segment.get("start"))
            end = _format_time(segment.get("end"))
            text = str(segment.get("text", "")).strip()
            for sentence in _split_sentences(text):
                lines.append(f"[{start} - {end}] {speaker}: {sentence}")
        return "\n".join(lines)

    return str(response_data.get("text", "")).strip()


def _speaker_name(speaker: Any, speaker_labels: dict[str, str]) -> str:
    raw = str(speaker or "Speaker").strip() or "Speaker"
    normalized = raw.removeprefix("Speaker ").strip()
    mapped = speaker_labels.get(raw) or speaker_labels.get(normalized)
    if mapped:
        return mapped
    if raw.lower().startswith("speaker "):
        return raw
    if len(raw) == 1 and raw.isalpha():
        return f"Speaker {raw}"
    return raw


def _parse_speaker_labels(value: str | None) -> dict[str, str]:
    if not value:
        return {}

    labels = {}
    for item in value.split(","):
        if "=" not in item:
            continue
        key, label = item.split("=", 1)
        key = key.strip()
        label = label.strip()
        if key and label:
            labels[key] = label
    return labels


def _parse_known_speakers(values: tuple[str, ...]) -> list[tuple[str, Path]]:
    known_speakers = []
    for value in values:
        if "=" not in value:
            raise ValueError(
                f"Invalid known speaker value '{value}'. Use Name=/path/to/sample.wav."
            )
        name, path_value = value.split("=", 1)
        name = name.strip()
        path = Path(path_value.strip()).expanduser().resolve()
        if not name:
            raise ValueError("Known speaker name cannot be empty.")
        if not path.is_file():
            raise FileNotFoundError(f"Known speaker reference does not exist: {path}")
        known_speakers.append((name, path))

    if len(known_speakers) > 4:
        raise ValueError("OpenAI diarization supports up to 4 known speaker references.")
    return known_speakers


def _split_sentences(text: str) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    sentences = []
    start = 0
    for index, char in enumerate(text):
        if char in ".!?" and (index + 1 == len(text) or text[index + 1].isspace()):
            sentence = text[start : index + 1].strip()
            if sentence:
                sentences.append(sentence)
            start = index + 1
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _format_time(value: Any) -> str:
    try:
        seconds = max(0, float(value))
    except (TypeError, ValueError):
        return "00:00:00"

    whole = int(seconds)
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
