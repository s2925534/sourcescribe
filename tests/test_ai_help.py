from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from transcriber_mvp.ai_help import _create_response, _resolve_transcript_path, split_text


class AIHelpTests(unittest.TestCase):
    def test_split_text_keeps_chunks_under_limit_when_possible(self) -> None:
        first = "a" * 1200
        second = "b" * 1200
        text = f"{first}\n\n{second}"

        chunks = split_text(text, 2000)

        self.assertEqual(chunks, [first, second])

    def test_resolve_transcript_path_accepts_completed_job_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp) / "completed" / "meeting"
            job_dir.mkdir(parents=True)
            transcript = job_dir / "transcript.txt"
            transcript.write_text("hello", encoding="utf-8")

            self.assertEqual(_resolve_transcript_path(job_dir), transcript.resolve())

    def test_create_response_rewrites_quota_error(self) -> None:
        class Responses:
            def create(self, **kwargs):
                raise Exception("insufficient_quota: You exceeded your current quota")

        class Client:
            responses = Responses()

        with self.assertRaisesRegex(RuntimeError, "no available quota"):
            _create_response(
                Client(),
                model="test",
                instructions="test",
                input_text="test",
            )


if __name__ == "__main__":
    unittest.main()
