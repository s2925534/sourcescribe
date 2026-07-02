from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from transcriber_mvp.openai_backend import (
    DEFAULT_LOCAL_MODEL,
    TranscriptionConfig,
    TranscriptionPayload,
)


def transcribe_media_local(
    media_path: Path,
    output_dir: Path,
    config: TranscriptionConfig,
) -> TranscriptionPayload:
    whisper_bin = shutil.which("whisper")
    if not whisper_bin:
        raise RuntimeError(
            "Local transcription requires the Whisper CLI, but no 'whisper' "
            "command was found on PATH. Install local Whisper or rerun with --ai."
        )

    whisper_output_dir = output_dir / "local_whisper"
    whisper_output_dir.mkdir(parents=True, exist_ok=True)
    local_model = config.local_model or DEFAULT_LOCAL_MODEL

    command = [
        whisper_bin,
        str(media_path),
        "--model",
        local_model,
        "--output_dir",
        str(whisper_output_dir),
        "--output_format",
        "json",
        "--task",
        "transcribe",
        "--verbose",
        "False",
    ]
    if config.language:
        command.extend(["--language", config.language])
    if config.prompt:
        command.extend(["--initial_prompt", config.prompt])
    if config.local_device:
        command.extend(["--device", config.local_device])

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown error").strip()
        raise RuntimeError(f"Local Whisper transcription failed: {detail[-4000:]}")

    raw_path = _find_whisper_json(whisper_output_dir, media_path)
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    raw["backend"] = {
        "name": "local_whisper",
        "model": local_model,
        "command": command,
    }
    text = str(raw.get("text", "")).strip()
    return TranscriptionPayload(text=text, raw=raw, chunks=[])


def _find_whisper_json(output_dir: Path, media_path: Path) -> Path:
    expected = output_dir / f"{media_path.stem}.json"
    if expected.exists():
        return expected

    candidates = sorted(output_dir.glob("*.json"), key=lambda path: path.stat().st_mtime)
    if candidates:
        return candidates[-1]

    raise RuntimeError(f"Local Whisper did not write a JSON transcript in {output_dir}")
