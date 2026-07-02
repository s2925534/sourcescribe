from __future__ import annotations

import unittest

from transcriber_mvp.openai_backend import (
    TranscriptionConfig,
    _parse_speaker_labels,
    _response_to_text,
)


class OpenAIBackendTests(unittest.TestCase):
    def test_diarized_response_is_speaker_prefixed_per_sentence(self) -> None:
        response = {
            "segments": [
                {
                    "speaker": "A",
                    "start": 1.2,
                    "end": 4.8,
                    "text": "Hello there. How are you?",
                },
                {
                    "speaker": "B",
                    "start": 5,
                    "end": 6,
                    "text": "Good thanks",
                },
            ]
        }

        text = _response_to_text(
            response,
            TranscriptionConfig(diarize=True, speaker_labels="A=Pedro,B=Supervisor"),
        )

        self.assertEqual(
            text,
            "\n".join(
                [
                    "[00:00:01 - 00:00:04] Pedro: Hello there.",
                    "[00:00:01 - 00:00:04] Pedro: How are you?",
                    "[00:00:05 - 00:00:06] Supervisor: Good thanks",
                ]
            ),
        )

    def test_parse_speaker_labels(self) -> None:
        self.assertEqual(
            _parse_speaker_labels("A=Pedro, B=Supervisor"),
            {"A": "Pedro", "B": "Supervisor"},
        )


if __name__ == "__main__":
    unittest.main()
