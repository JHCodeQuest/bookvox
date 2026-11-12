import os
import tempfile
import unittest
from unittest.mock import patch

from phonemizer.backend.espeak.wrapper import EspeakWrapper
from bookvox.core import set_espeak_library


class EspeakLibraryTests(unittest.TestCase):
    def setUp(self):
        self.original_library = EspeakWrapper.library()

    def tearDown(self):
        EspeakWrapper.set_library(self.original_library)

    def test_default_preserves_misaki_library(self):
        with patch.dict(os.environ, {}, clear=True):
            set_espeak_library()
        self.assertEqual(EspeakWrapper.library(), self.original_library)

    def test_valid_override_is_applied(self):
        with patch.dict(os.environ, {"ESPEAK_LIBRARY": str(self.original_library)}):
            set_espeak_library()
        self.assertTrue(os.path.samefile(EspeakWrapper.library(), self.original_library))

    def test_removing_override_restores_bundled_library(self):
        with patch.dict(os.environ, {"ESPEAK_LIBRARY": str(self.original_library)}):
            set_espeak_library()
        with patch.dict(os.environ, {}, clear=True):
            with patch("espeakng_loader.get_library_path", return_value="bundled-library"):
                set_espeak_library()
        self.assertEqual(EspeakWrapper.library(), "bundled-library")

    def test_missing_override_fails(self):
        with patch.dict(os.environ, {"ESPEAK_LIBRARY": "missing-espeak-library"}):
            with self.assertRaisesRegex(RuntimeError, "ESPEAK_LIBRARY"):
                set_espeak_library()

    def test_unloadable_override_fails(self):
        handle, junk = tempfile.mkstemp(suffix='.dll')
        with os.fdopen(handle, 'w') as f:
            f.write('not a library')
        try:
            with patch.dict(os.environ, {"ESPEAK_LIBRARY": junk}):
                with self.assertRaisesRegex(RuntimeError, "ESPEAK_LIBRARY"):
                    set_espeak_library()
        finally:
            os.unlink(junk)


if __name__ == "__main__":
    unittest.main()
