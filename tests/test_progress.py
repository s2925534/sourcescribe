from __future__ import annotations

import unittest

from transcriber_mvp.progress import _parse_tqdm_line


class ProgressTests(unittest.TestCase):
    def test_parses_frame_progress(self) -> None:
        self.assertEqual(
            _parse_tqdm_line(" 42%|####      | 420/1000 [00:02<00:03, 145frames/s]"),
            (420, 1000),
        )

    def test_parses_download_progress(self) -> None:
        self.assertEqual(
            _parse_tqdm_line("  6%|## | 4.41M/72.1M [00:00<00:03, 19.3MiB/s]"),
            (4_410_000, 72_100_000),
        )


if __name__ == "__main__":
    unittest.main()
