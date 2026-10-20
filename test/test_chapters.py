import json
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

import ebooklib
import numpy as np
import soundfile
from ebooklib import epub

from bookvox.core import create_index_file, create_m4b, find_toc_titles

MINI_EPUB = Path(__file__).resolve().parent.parent / 'epub' / 'mini.epub'


def m4b_chapter_titles(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_chapters', '-of', 'json', str(path)],
                         capture_output=True, text=True, encoding='utf-8', check=True).stdout
    return [c['tags']['title'] for c in json.loads(out)['chapters']]


def m4b_tags(path):
    """The file's own tags and its chapter titles, as ffprobe reports them."""
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_chapters', '-of', 'json', str(path)],
                         capture_output=True, text=True, encoding='utf-8', check=True).stdout
    data = json.loads(out)
    return data['format']['tags'], [c['tags']['title'] for c in data['chapters']]


def tiny_wav(path):
    tone = (0.1 * np.sin(np.linspace(0, 2 * np.pi * 88, 4800))).astype('float32')  # 0.2 s at 24 kHz
    soundfile.write(path, tone, 24000)


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

    def test_percent_encoded_toc_links_still_match_the_chapter_names(self):
        # Most epub tools write a space as %20 in the links; ebooklib decodes the chapter names but not the TOC.
        book = epub.EpubBook()
        book.set_identifier('x'), book.set_title('T'), book.set_language('en')
        chapter = epub.EpubHtml(title='My Real Title', file_name='My Chapter.xhtml', lang='en')
        chapter.content = '<h1>My Real Title</h1><p>text</p>'
        book.add_item(chapter)
        book.toc = (epub.Link('My Chapter.xhtml', 'My Real Title', 'u'),)
        book.add_item(epub.EpubNcx()), book.add_item(epub.EpubNav())
        book.spine = ['nav', chapter]
        plain, encoded = self.tmp / 'plain.epub', self.tmp / 'encoded.epub'
        epub.write_epub(str(plain), book)
        with zipfile.ZipFile(plain) as zin, zipfile.ZipFile(encoded, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.endswith(('.opf', '.ncx', 'nav.xhtml')):
                    data = data.replace(b'My Chapter.xhtml', b'My%20Chapter.xhtml')
                zout.writestr(item, data)
        names = [i.get_name() for i in epub.read_epub(str(encoded)).get_items_of_type(ebooklib.ITEM_DOCUMENT)]
        self.assertIn('My Chapter.xhtml', names)  # the chapter name is decoded...
        self.assertEqual(find_toc_titles(epub.read_epub(str(encoded))).get('My Chapter.xhtml'), 'My Real Title')

    def test_newlines_and_special_characters_in_every_title_survive_in_the_m4b(self):
        files = self.wavs(2)
        create_index_file('Part One\nThe Return', 'Auth;or=#', files, str(self.tmp),
                          {files[0]: 'Line A\nLine B', files[1]: 'Plain'})
        create_m4b(files, 'Book.epub', b'', str(self.tmp))
        tags, chapters = m4b_tags(self.tmp / 'Book.m4b')
        self.assertEqual(tags['title'], 'Part One\nThe Return')
        self.assertEqual(tags['artist'], 'Auth;or=#')
        self.assertEqual(chapters, ['Line A\nLine B', 'Plain'])


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg not installed')
class MainChapterTitlesTest(unittest.TestCase):
    def test_titles_stay_with_their_audio_when_a_chapter_in_the_middle_is_skipped(self):
        from bookvox.core import find_document_chapters_and_extract_texts, main
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        book = epub.EpubBook()
        book.set_identifier('x'), book.set_title('T'), book.set_language('en')
        bodies = {'ch1.xhtml': ('First', '<p>The first chapter has enough text to count.</p>'),
                  'ch2.xhtml': ('Second', '<p>x</p>'),  # too short: main() skips it as empty
                  'ch3.xhtml': ('Third', '<p>The third chapter has enough text as well.</p>')}
        chapters = []
        for name, (title, body) in bodies.items():
            chapter = epub.EpubHtml(title=title, file_name=name, lang='en')
            chapter.content = body
            book.add_item(chapter)
            chapters.append(chapter)
        book.toc = tuple(epub.Link(c.file_name, c.title, c.file_name) for c in chapters)
        book.add_item(epub.EpubNcx()), book.add_item(epub.EpubNav())
        book.spine = ['nav'] + chapters
        path = tmp / 'book.epub'
        epub.write_epub(str(path), book)
        out = tmp / 'out'
        out.mkdir()
        for i, name in ((1, 'ch1.xhtml'), (3, 'ch3.xhtml')):  # audio that already exists is not re-synthesised
            tiny_wav(out / f'book_chapter_{i}_af_sky_{name}.wav')
        wanted = [c for c in find_document_chapters_and_extract_texts(epub.read_epub(str(path))) if c.get_name() in bodies]
        main(str(path), 'af_sky', False, 1.0, str(out), selected_chapters=wanted)
        self.assertEqual(m4b_tags(out / 'book.m4b')[1], ['First', 'Third'])
