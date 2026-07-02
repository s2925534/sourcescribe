from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from transcriber_mvp.openai_backend import TranscriptionConfig, TranscriptionPayload
from transcriber_mvp.workflow import JobConfig, run_jobs


def fake_transcriber(
    media_path: Path,
    output_dir: Path,
    config: TranscriptionConfig,
) -> TranscriptionPayload:
    return TranscriptionPayload(
        text=f"Transcript for {media_path.name}",
        raw={"model": config.model, "file": media_path.name},
        chunks=[],
    )


class WorkflowTests(unittest.TestCase):
    def test_source_file_is_moved_into_completed_job_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "source"
            source_dir.mkdir()
            media = source_dir / "weekly-meeting.m4a"
            media.write_bytes(b"audio")

            results = run_jobs(
                JobConfig(source_dir=source_dir, media_arg=str(media)),
                transcriber=fake_transcriber,
            )

            self.assertEqual(results[0].status, "completed")
            output_dir = source_dir / "completed" / "weekly-meeting"
            self.assertTrue((output_dir / "weekly-meeting.m4a").exists())
            self.assertFalse(media.exists())
            self.assertEqual(
                (output_dir / "transcript.txt").read_text(encoding="utf-8").strip(),
                "Transcript for weekly-meeting.m4a",
            )

            report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
            self.assertTrue(report["input_was_inside_source_dir"])
            self.assertTrue(report["source_was_moved"])

    def test_external_file_is_transcribed_but_not_moved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            source_dir.mkdir()
            external = root / "external.m4a"
            external.write_bytes(b"audio")

            results = run_jobs(
                JobConfig(source_dir=source_dir, media_arg=str(external)),
                transcriber=fake_transcriber,
            )

            self.assertEqual(results[0].status, "completed")
            output_dir = source_dir / "completed" / "external"
            self.assertTrue(external.exists())
            self.assertFalse((output_dir / "external.m4a").exists())

            report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
            self.assertFalse(report["input_was_inside_source_dir"])
            self.assertFalse(report["source_was_moved"])

    def test_missing_file_gets_failure_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "source"
            missing = Path(tmp) / "missing.m4a"

            results = run_jobs(
                JobConfig(source_dir=source_dir, media_arg=str(missing)),
                transcriber=fake_transcriber,
            )

            self.assertEqual(results[0].status, "failed")
            output_dir = source_dir / "completed" / "missing"
            report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")
            self.assertIn("does not exist", report["error"])

    def test_default_backend_is_local(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "source"
            source_dir.mkdir()
            media = source_dir / "meeting.m4a"
            media.write_bytes(b"audio")

            with patch("transcriber_mvp.workflow.transcribe_media_local") as transcriber:
                transcriber.return_value = TranscriptionPayload(
                    text="Local transcript",
                    raw={"backend": "local"},
                    chunks=[],
                )

                results = run_jobs(JobConfig(source_dir=source_dir, media_arg=str(media)))

            self.assertEqual(results[0].status, "completed")
            transcriber.assert_called_once()

    def test_ai_flag_selects_openai_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_dir = Path(tmp) / "source"
            source_dir.mkdir()
            media = source_dir / "meeting.m4a"
            media.write_bytes(b"audio")

            with patch("transcriber_mvp.workflow.transcribe_media") as transcriber:
                transcriber.return_value = TranscriptionPayload(
                    text="OpenAI transcript",
                    raw={"backend": "openai"},
                    chunks=[],
                )

                results = run_jobs(
                    JobConfig(source_dir=source_dir, media_arg=str(media), use_ai=True)
                )

            self.assertEqual(results[0].status, "completed")
            transcriber.assert_called_once()


if __name__ == "__main__":
    unittest.main()
