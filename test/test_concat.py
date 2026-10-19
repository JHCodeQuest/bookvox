import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile

from bookvox.core import create_m4b

BOOK_BYTES = b'not really an epub, but it must survive'


@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg not installed')
class CreateM4bFilenamesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def make_book_and_chapters(self, book_name, chapter_names):
        """Put a fake book and tiny chapter wavs side by side, like the default output folder '.'."""
        book = self.tmp / book_name
        book.write_bytes(BOOK_BYTES)
        tone = (0.1 * np.sin(np.linspace(0, 2 * np.pi * 88, 4800))).astype('float32')  # 0.2 s at 24 kHz
        chapters = []
        for name in chapter_names:
            soundfile.write(self.tmp / name, tone, 24000)
            chapters.append(self.tmp / name)
        (self.tmp / 'chapters.txt').write_text(';FFMETADATA1\ntitle=t\n', encoding='utf-8')
        return book, chapters

    def test_uppercase_epub_extension_keeps_the_source_book(self):
        book, chapters = self.make_book_and_chapters('Book.EPUB', ['a.wav', 'b.wav'])
        create_m4b(chapters, book.name, b'', str(self.tmp))
        self.assertEqual(book.read_bytes(), BOOK_BYTES)
        self.assertGreater((self.tmp / 'Book.m4b').stat().st_size, 0)
