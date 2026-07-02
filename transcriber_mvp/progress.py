from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
BOLD = "\033[1m"
RESET = "\033[0m"


def color(text: str, code: str, stream: TextIO | None = None) -> str:
    stream = stream or sys.stdout
    if not _supports_color(stream):
        return text
    return f"{code}{text}{RESET}"


def print_progress(
    label: str,
    current: int,
    total: int,
    started_at: float,
    *,
    stream: TextIO | None = None,
    done: bool = False,
) -> None:
    stream = stream or sys.stderr
    current = max(0, current)
    total = max(1, total)
    ratio = min(1.0, current / total)
    width = 28
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    elapsed = max(0.0, time.monotonic() - started_at)
    eta = _eta(elapsed, current, total)
    pct = int(ratio * 100)

    if _supports_color(stream):
        bar = color("#" * filled, GREEN, stream) + "-" * (width - filled)
        label = color(label, BLUE, stream)

    line = (
        f"\r{label} [{bar}] {pct:3d}% "
        f"{current}/{total} elapsed {_format_duration(elapsed)} eta {eta}"
    )
    stream.write(line + (" " * 8))
    if done:
        stream.write("\n")
    stream.flush()


def run_with_tqdm_progress(
    command: list[str],
    *,
    env: dict[str, str],
    label: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    started_at = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        env=env,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None

    tail: list[str] = []
    buffer = ""
    last_progress: tuple[int, int] | None = None
    for char in iter(lambda: process.stdout.read(1), ""):
        buffer += char
        if char not in {"\r", "\n"}:
            continue

        line = buffer.strip()
        buffer = ""
        if not line:
            continue

        tail.append(line)
        tail = tail[-40:]
        parsed = _parse_tqdm_line(line)
        if parsed:
            current, total = parsed
            last_progress = current, total
            print_progress(label, current, total, started_at)
        elif _should_show_line(line):
            sys.stderr.write(f"\n{line}\n")
            sys.stderr.flush()

    if buffer.strip():
        tail.append(buffer.strip())
        tail = tail[-40:]

    returncode = process.wait()
    if last_progress:
        current, total = last_progress
        print_progress(label, total if returncode == 0 else current, total, started_at, done=True)

    output_tail = "\n".join(tail)
    return subprocess.CompletedProcess(
        args=command,
        returncode=returncode,
        stdout="",
        stderr=output_tail,
    )


def _parse_tqdm_line(line: str) -> tuple[int, int] | None:
    matches = re.findall(r"(?<![\d.])(\d+)\s*/\s*(\d+)(?![\d.])", line)
    if matches:
        current, total = matches[-1]
        total_int = int(total)
        if total_int <= 0:
            return None
        return min(int(current), total_int), total_int

    byte_match = re.search(
        r"(?<![\d.])(\d+(?:\.\d+)?)([KMGT]?)i?B?"
        r"\s*/\s*"
        r"(\d+(?:\.\d+)?)([KMGT]?)i?B?(?![\d.])",
        line,
    )
    if not byte_match:
        return None

    current = _scaled_number(byte_match.group(1), byte_match.group(2))
    total_int = _scaled_number(byte_match.group(3), byte_match.group(4))
    if total_int <= 0:
        return None
    return min(current, total_int), total_int


def _scaled_number(value: str, suffix: str) -> int:
    scale = {
        "": 1,
        "K": 1_000,
        "M": 1_000_000,
        "G": 1_000_000_000,
        "T": 1_000_000_000_000,
    }[suffix]
    return int(float(value) * scale)


def _eta(elapsed: float, current: int, total: int) -> str:
    if current <= 0:
        return "--:--"
    remaining = (elapsed / current) * max(0, total - current)
    return _format_duration(remaining)


def _format_duration(seconds: float) -> str:
    whole = int(seconds)
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _should_show_line(line: str) -> bool:
    lowered = line.lower()
    return "warning" in lowered or "error" in lowered or "failed" in lowered


def _supports_color(stream: TextIO) -> bool:
    return hasattr(stream, "isatty") and stream.isatty() and not os.getenv("NO_COLOR")
