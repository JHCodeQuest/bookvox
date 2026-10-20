"""Progress accounting for the intro text.

The intro (`"<title> – <author>.\n\n"`) is narrated in front of chapter 1 but is not part
of any chapter's text, so it was never part of `total_chars`. Its characters were counted
as processed anyway, which pushed `processed_chars * 100 // total_chars` above 100 on
short books (progress is now clamped to 100 as a second line of defence).

The heavy TTS dependencies (torch, spacy, kokoro, soundfile, ...) are stubbed so this
test runs on a bare Python; only the pure accounting logic is under test.
"""
import sys
import types
import unittest
from types import SimpleNamespace


def _stub_module(name):
    module = types.ModuleType(name)
    module.__getattr__ = lambda attr: (lambda *a, **k: None)
    sys.modules[name] = module
    return module


for _name in ('torch', 'torch.cuda', 'spacy', 'spacy.util', 'spacy.cli', 'ebooklib',
              'ebooklib.epub', 'soundfile', 'numpy', 'kokoro', 'pick', 'bs4', 'tabulate'):
    _stub_module(_name)

from bookvox.core import compute_progress


class ProgressTest(unittest.TestCase):
    def _stats(self, total_chars, processed_chars=0):
        return SimpleNamespace(total_chars=total_chars, processed_chars=processed_chars)

    def test_finished_book_reaches_exactly_100(self):
        # chapter text plus intro processed
        stats = self._stats(total_chars=913, processed_chars=913)
        self.assertEqual(compute_progress(stats), 100)

    def test_progress_is_clamped_at_100(self):
        # processed beyond total (bad arithmetic upstream) may never raise the bar over 100
        stats = self._stats(total_chars=900, processed_chars=913)
        self.assertLessEqual(compute_progress(stats), 100)
        self.assertEqual(compute_progress(stats), 100)

    def test_overshoot_regression(self):
        # a ~900-char chapter with a 13-char intro: the old unclamped
        # formula reported 102 percent here
        stats = self._stats(total_chars=900, processed_chars=913)
        self.assertNotEqual(stats.processed_chars * 100 // stats.total_chars, 100)
        self.assertEqual(compute_progress(stats), 100)

    def test_progress_floors_partly_processed(self):
        stats = self._stats(total_chars=1000, processed_chars=250)
        self.assertEqual(compute_progress(stats), 25)


if __name__ == '__main__':
    unittest.main()
