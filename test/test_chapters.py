import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile
from ebooklib import epub

from bookvox.core import create_index_file, create_m4b

MINI_EPUB = Path(__file__).resolve().parent.parent / 'epub' / 'mini.epub'


def m4b_chapter_titles(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_chapters', '-of', 'json', str(path)],
                         capture_output=True, text=True, encoding='utf-8', check=True).stdout
    return [c['tags']['title'] for c in json.loads(out)['chapters']]


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg not installed')
class ChapterTitlesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def wavs(self, count):
        tone = (0.1 * np.sin(np.linspace(0, 2 * np.pi * 88, 4800))).astype('float32')  # 0.2 s at 24 kHz
        files = []
        for i in range(count):
            path = self.tmp / f'ch{i}.wav'
            soundfile.write(path, tone, 24000)
            files.append(path)
        return files

    def index_titles(self, files, chapter_titles=None):
        extra = () if chapter_titles is None else (chapter_titles,)
        create_index_file('Book', 'Author', files, str(self.tmp), *extra)
        text = (self.tmp / 'chapters.txt').read_text(encoding='utf-8')
        return re.findall(r'^title=(.*)$', text, re.M)[1:]  # the first title= line is the book's own

    def test_chapter_numbers_start_at_one(self):
        self.assertEqual(self.index_titles(self.wavs(2)), ['Chapter 1', 'Chapter 2'])

    def test_the_books_own_chapter_titles_are_used(self):
        files = self.wavs(2)
        self.assertEqual(self.index_titles(files, {files[0]: 'The Beginning', files[1]: 'The End'}),
                         ['The Beginning', 'The End'])

    def test_a_chapter_without_a_title_falls_back_to_its_number(self):
        files = self.wavs(2)
        self.assertEqual(self.index_titles(files, {files[1]: 'The End'}), ['Chapter 1', 'The End'])

    def test_titles_with_special_characters_survive_in_the_m4b(self):
        # ffmpeg's metadata file needs = ; # backslash and newline escaped
        files = self.wavs(2)
        tricky = 'A=B; C #1 \\ D'
        create_index_file('Book', 'Author', files, str(self.tmp), {files[0]: tricky, files[1]: 'Plain'})
        create_m4b(files, 'Book.epub', b'', str(self.tmp))
        self.assertEqual(m4b_chapter_titles(self.tmp / 'Book.m4b'), [tricky, 'Plain'])

    def test_titles_come_from_the_epub_toc(self):
        from bookvox.core import find_toc_titles
        book = epub.read_epub(str(MINI_EPUB))
        self.assertEqual(find_toc_titles(book), {'ch1.xhtml': 'Chapter One', 'ch2.xhtml': 'Chapter Two'})

    def test_nested_toc_entries_and_messy_whitespace_are_handled(self):
        from bookvox.core import find_toc_titles
        book = epub.EpubBook()
        book.toc = (
            epub.Link('a.xhtml', '  Part\n One ', 'a'),
            (epub.Section('Part Two', href='b.xhtml'), [epub.Link('c.xhtml#frag', 'Deep chapter', 'c')]),
            epub.Link('d.xhtml', '   ', 'd'),  # blank title: ignored
        )
        self.assertEqual(find_toc_titles(book),
                         {'a.xhtml': 'Part One', 'b.xhtml': 'Part Two', 'c.xhtml': 'Deep chapter'})
