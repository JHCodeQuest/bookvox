"""Progress accounting for the intro text.

The intro (`"<title> – <author>.\n\n"`) is narrated in front of chapter 1 but is not part
of any chapter's text, so it was never part of `total_chars`. Its characters were counted
as processed anyway, which pushed `processed_chars * 100 // total_chars` above 100 on
short books (progress is now clamped to 100 as a second line of defence).

The heavy TTS dependencies (torch, spacy, kokoro, soundfile, ...) are stubbed only when
missing, so this test runs on a bare Python; only the pure accounting logic is under test.
"""
import importlib.util
import sys
import types
import unittest
from types import SimpleNamespace

# The heavy TTS dependencies are stubbed only when genuinely missing, so this test runs
# on a bare Python without ever shadowing a real module (or one another test file loaded).
HEAVY_IMPORTS = ('torch', 'torch.cuda', 'spacy', 'spacy.util', 'spacy.cli', 'ebooklib',
                 'ebooklib.epub', 'soundfile', 'numpy', 'kokoro', 'pick', 'bs4', 'tabulate')


def _stub_module():
    module = types.ModuleType('')
    module.__getattr__ = lambda attr: (lambda *a, **k: None)
    return module


_stubs = {}
for _name in HEAVY_IMPORTS:
    if _name in sys.modules:
        continue  # real module already loaded: never shadow it
    try:
        if importlib.util.find_spec(_name) is not None:
            continue  # real module installed
    except (ImportError, ValueError):
        pass
    _stubs[_name] = _stub_module()
sys.modules.update(_stubs)

try:
    from bookvox.core import compute_progress
finally:
    # With stubs in play, drop them and the copy of bookvox.core they were loaded with,
    # so other test files import the real dependencies instead of a stub-rigged module.
    if _stubs:
        for _name in _stubs:
            sys.modules.pop(_name, None)
        sys.modules.pop('bookvox.core', None)


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
