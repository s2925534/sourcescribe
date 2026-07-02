from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from transcriber_mvp.progress import print_progress


DEFAULT_AI_HELP_MODEL = "auto"
DEFAULT_AI_HELP_CHUNK_CHARS = 12000
PREFERRED_TEXT_MODELS = (
    "gpt-5-mini",
    "gpt-5",
    "gpt-4.1-mini",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4o",
)


@dataclass(frozen=True)
class AIHelpConfig:
    model: str = DEFAULT_AI_HELP_MODEL
    chunk_chars: int = DEFAULT_AI_HELP_CHUNK_CHARS


@dataclass(frozen=True)
class AIHelpResult:
    transcript_path: Path
    output_dir: Path
    cleaned_transcript_path: Path
    summary_path: Path
    action_items_path: Path
    report_path: Path
    model: str


def run_ai_help_for_path(path: Path, config: AIHelpConfig) -> AIHelpResult:
    transcript_path = _resolve_transcript_path(path)
    output_dir = transcript_path.parent / "ai_help"
    return run_ai_help(transcript_path, output_dir, config)


def run_ai_help(
    transcript_path: Path,
    output_dir: Path,
    config: AIHelpConfig,
) -> AIHelpResult:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set in the environment or .env file.")

    transcript_path = transcript_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_text = transcript_path.read_text(encoding="utf-8-sig")
    chunks = split_text(raw_text, config.chunk_chars)

    from openai import OpenAI

    client = OpenAI()
    model = _resolve_model(client, config.model)
    started_at = time.monotonic()
    cleaned_chunks = []

    for index, chunk in enumerate(chunks, start=1):
        print_progress("ai cleanup", index - 1, len(chunks), started_at, stream=sys.stderr)
        cleaned_chunks.append(_clean_chunk(client, model, chunk, index, len(chunks)))
        print_progress(
            "ai cleanup",
            index,
            len(chunks),
            started_at,
            stream=sys.stderr,
            done=index == len(chunks),
        )

    cleaned_text = "\n\n".join(part.strip() for part in cleaned_chunks if part.strip())
    summary = _summarize(client, model, cleaned_text)
    action_items = _extract_action_items(client, model, cleaned_text)

    cleaned_path = output_dir / "transcript_ai_cleaned.md"
    summary_path = output_dir / "meeting_summary.md"
    action_items_path = output_dir / "action_items.md"
    report_path = output_dir / "ai_help_report.json"

    cleaned_path.write_text(cleaned_text.rstrip() + "\n", encoding="utf-8")
    summary_path.write_text(summary.rstrip() + "\n", encoding="utf-8")
    action_items_path.write_text(action_items.rstrip() + "\n", encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "model": model,
                "source_transcript_path": str(transcript_path),
                "output_dir": str(output_dir),
                "chunk_count": len(chunks),
                "chunk_chars": config.chunk_chars,
                "cleaned_transcript_path": str(cleaned_path),
                "summary_path": str(summary_path),
                "action_items_path": str(action_items_path),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return AIHelpResult(
        transcript_path=transcript_path,
        output_dir=output_dir,
        cleaned_transcript_path=cleaned_path,
        summary_path=summary_path,
        action_items_path=action_items_path,
        report_path=report_path,
        model=model,
    )


def split_text(text: str, chunk_chars: int) -> list[str]:
    chunk_chars = max(2000, chunk_chars)
    paragraphs = [part.strip() for part in text.splitlines() if part.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        extra = len(paragraph) + 2
        if current and current_len + extra > chunk_chars:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0

        if len(paragraph) > chunk_chars:
            chunks.extend(_split_long_paragraph(paragraph, chunk_chars))
            continue

        current.append(paragraph)
        current_len += extra

    if current:
        chunks.append("\n\n".join(current))
    return chunks or [text.strip()]


def _split_long_paragraph(paragraph: str, chunk_chars: int) -> list[str]:
    return [
        paragraph[index : index + chunk_chars]
        for index in range(0, len(paragraph), chunk_chars)
    ]


def _resolve_transcript_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.is_dir():
        transcript = resolved / "transcript.txt"
        if transcript.exists():
            return transcript
        raise FileNotFoundError(f"No transcript.txt found in {resolved}")
    if not resolved.exists():
        raise FileNotFoundError(f"Transcript path does not exist: {resolved}")
    return resolved


def _resolve_model(client: Any, configured_model: str) -> str:
    if configured_model and configured_model != "auto":
        return configured_model

    try:
        models = client.models.list()
        available = {model.id for model in models.data}
    except Exception:
        return "gpt-4o-mini"

    for candidate in PREFERRED_TEXT_MODELS:
        if candidate in available:
            return candidate
    return "gpt-4o-mini"


def _clean_chunk(
    client: Any,
    model: str,
    chunk: str,
    index: int,
    total: int,
) -> str:
    instructions = (
        "You clean raw meeting transcripts. Preserve meaning and speaker intent. "
        "Fix punctuation, paragraphing, obvious speech-recognition errors, and "
        "obvious repeated hallucinations. Do not invent facts, names, decisions, "
        "or action items. Keep uncertainty as [unclear]. Return only the cleaned "
        "transcript text for this chunk."
    )
    return _response_text(
        _create_response(
            client,
            model=model,
            instructions=instructions,
            input_text=(
                f"Clean transcript chunk {index} of {total}.\n\n"
                f"Raw transcript chunk:\n{chunk}"
            ),
        )
    )


def _summarize(client: Any, model: str, cleaned_text: str) -> str:
    instructions = (
        "You turn meeting transcripts into concise, faithful Markdown notes. "
        "Do not invent details. If a point is uncertain, say so."
    )
    return _response_text(
        _create_response(
            client,
            model=model,
            instructions=instructions,
            input_text=(
                "Create meeting notes from this transcript with these sections:\n"
                "## Overview\n## Key Discussion Points\n## Decisions\n"
                "## Risks or Blockers\n## Follow-ups\n## Transcript Quality Notes\n\n"
                f"Transcript:\n{cleaned_text}"
            ),
        )
    )


def _extract_action_items(client: Any, model: str, cleaned_text: str) -> str:
    instructions = (
        "Extract only explicit or strongly implied action items from meeting "
        "transcripts. Use Markdown. Do not invent owners or deadlines."
    )
    return _response_text(
        _create_response(
            client,
            model=model,
            instructions=instructions,
            input_text=(
                "Extract action items as a Markdown table with columns: "
                "Action, Owner, Due Date, Evidence. Use 'Unclear' when missing.\n\n"
                f"Transcript:\n{cleaned_text}"
            ),
        )
    )


def _create_response(
    client: Any,
    *,
    model: str,
    instructions: str,
    input_text: str,
) -> Any:
    try:
        return client.responses.create(
            model=model,
            instructions=instructions,
            input=input_text,
        )
    except Exception as exc:
        message = str(exc)
        if "insufficient_quota" in message or "exceeded your current quota" in message:
            raise RuntimeError(
                "OpenAI rejected the request because the current key has no "
                "available quota. Check the API key's project billing and limits."
            ) from exc
        if "incorrect api key" in message.lower() or "invalid api key" in message.lower():
            raise RuntimeError(
                "OpenAI rejected the request because the API key is invalid."
            ) from exc
        raise


def _response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text).strip()

    data = response.model_dump(mode="json") if hasattr(response, "model_dump") else response
    texts: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                texts.append(text)
    return "\n".join(texts).strip()
