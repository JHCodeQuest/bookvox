import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # lets the tests run from the repo root too
from epub_factory import build_epub

from ebooklib import epub

from bookvox.core import find_document_chapters_and_extract_texts, find_good_chapters

REPO = Path(__file__).resolve().parent.parent


def optional_book(name):
    """Skip cleanly when a real book is not in the repo: the epubs under epub/ are not committed."""
    path = REPO / 'epub' / f'{name}.epub'
    return unittest.skipUnless(path.exists(), f'optional book epub/{name}.epub is not in the repo; '
                                              f'place it there to run this test')


class FindChaptersTest(unittest.TestCase):
    def setUp(self):
        # rmtree(ignore_errors): ebooklib's read_epub leaves the zip open, which Windows forbids deleting.
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def synthetic_chapters(self, documents):
        build_epub(self.tmp / 'book.epub', documents)
        book = epub.read_epub(str(self.tmp / 'book.epub'))
        return find_good_chapters(find_document_chapters_and_extract_texts(book))

    def real_chapters(self, name):
        book = epub.read_epub(str(REPO / 'epub' / f'{name}.epub'))
        return find_good_chapters(find_document_chapters_and_extract_texts(book))

    def test_selects_chapter_named_documents_with_enough_text(self):
        chapters = self.synthetic_chapters([
            ('cover.xhtml', 'A cover.'),                      # short: too little text
            ('contents.xhtml', 'Table of contents. ' * 10),   # long but not chapter-named
            ('ch01.xhtml', 'Chapter one text. ' * 10),
            ('chapter_02.xhtml', 'Chapter two text. ' * 10),
        ])
        self.assertEqual([c.get_name() for c in chapters], ['ch01.xhtml', 'chapter_02.xhtml'])

    def test_excludes_documents_with_too_little_text(self):
        chapters = self.synthetic_chapters([
            ('ch01.xhtml', 'Too short.'),
            ('ch02.xhtml', 'Long enough. ' * 15),
        ])
        self.assertEqual([c.get_name() for c in chapters], ['ch02.xhtml'])

    def test_fallback_selects_all_non_empty_documents(self):
        # If no document looks like a chapter, all non-empty ones are selected (like Dracula).
        # nav.xhtml: ebooklib adds the navigation document, its text passes the 10-char cutoff.
        chapters = self.synthetic_chapters([
            (f'section_{i}.xhtml', f'Section {i} text. ' * 10) for i in (1, 2, 3)
        ])
        self.assertEqual([c.get_name() for c in chapters],
                         ['section_1.xhtml', 'section_2.xhtml', 'section_3.xhtml', 'nav.xhtml'])

    def test_fallback_ignores_empty_documents(self):
        chapters = self.synthetic_chapters([
            ('section_1.xhtml', 'Enough text here. ' * 10),
            ('section_2.xhtml', ''),
        ])
        self.assertEqual([c.get_name() for c in chapters], ['section_1.xhtml', 'nav.xhtml'])

    # The tests below need real books that are not committed (copyright); they are skipped when absent.

    @optional_book('gene')
    def test_gene(self):
        self.assertEqual([c.get_name() for c in self.real_chapters('gene')], [
            '010_chapter.xhtml', '011_chapter.xhtml', '012_chapter.xhtml', '013_chapter.xhtml',
            '014_chapter.xhtml', '015_chapter.xhtml', '016_chapter.xhtml', '017_chapter.xhtml',
            '018_chapter.xhtml', '019_chapter.xhtml', '020_chapter.xhtml', '021_chapter.xhtml',
            '022_chapter.xhtml',
        ])

    @optional_book('lewis')
    def test_lewis_innocents(self):
        self.assertEqual([c.get_name() for c in self.real_chapters('lewis')], [
            'ch01.xhtml', 'ch02.xhtml', 'ch03.xhtml', 'ch04.xhtml', 'ch05.xhtml', 'ch06.xhtml',
            'ch07.xhtml', 'ch08.xhtml', 'ch09.xhtml', 'ch10.xhtml', 'ch11.xhtml', 'ch12.xhtml',
            'ch13.xhtml', 'ch14.xhtml', 'ch15.xhtml', 'ch16.xhtml', 'ch17.xhtml', 'ch18.xhtml',
        ])

    @optional_book('solenoid')
    def test_solenoid(self):
        self.assertEqual([c.get_name() for c in self.real_chapters('solenoid')], [
            'xhtml/part1.xhtml', 'xhtml/part2.xhtml', 'xhtml/part3.xhtml', 'xhtml/part4.xhtml',
        ])

    @optional_book('chalmers')
    def test_chalmers(self):
        self.assertEqual([c.get_name() for c in self.real_chapters('chalmers')], [
            'Text/12_Chapter01.xhtml', 'Text/12_Chapter02.xhtml', 'Text/12_Chapter03.xhtml',
            'Text/12_Chapter04.xhtml', 'Text/12_Chapter05.xhtml', 'Text/12_Chapter06.xhtml',
            'Text/12_Chapter07.xhtml', 'Text/12_Chapter08.xhtml', 'Text/12_Chapter09.xhtml',
            'Text/12_Chapter10.xhtml', 'Text/12_Chapter11.xhtml', 'Text/12_Chapter12.xhtml',
            'Text/12_Chapter13.xhtml', 'Text/12_Chapter14.xhtml', 'Text/12_Chapter15.xhtml',
            'Text/12_Chapter16.xhtml', 'Text/12_Chapter17.xhtml', 'Text/12_Chapter18.xhtml',
            'Text/12_Chapter19.xhtml', 'Text/12_Chapter20.xhtml', 'Text/12_Chapter21.xhtml',
            'Text/12_Chapter22.xhtml', 'Text/12_Chapter23.xhtml', 'Text/12_Chapter24.xhtml',
        ])

    @optional_book('dracula')
    def test_dracula_default_all_chapters(self):
        # If it cannot detect chapters, default to all available documents.
        self.assertEqual([c.get_name() for c in self.real_chapters('dracula')], [
            '2903486949112998543_345-h-0.htm.xhtml', '2903486949112998543_345-h-1.htm.xhtml',
            '2903486949112998543_345-h-2.htm.xhtml', '2903486949112998543_345-h-3.htm.xhtml',
            '2903486949112998543_345-h-4.htm.xhtml', '2903486949112998543_345-h-5.htm.xhtml',
            '2903486949112998543_345-h-6.htm.xhtml', '2903486949112998543_345-h-7.htm.xhtml',
            '2903486949112998543_345-h-8.htm.xhtml', '2903486949112998543_345-h-9.htm.xhtml',
            '2903486949112998543_345-h-10.htm.xhtml', '2903486949112998543_345-h-11.htm.xhtml',
            '2903486949112998543_345-h-12.htm.xhtml', '2903486949112998543_345-h-13.htm.xhtml',
            '2903486949112998543_345-h-14.htm.xhtml', '2903486949112998543_345-h-15.htm.xhtml',
            '2903486949112998543_345-h-16.htm.xhtml', '2903486949112998543_345-h-17.htm.xhtml',
            '2903486949112998543_345-h-18.htm.xhtml', '2903486949112998543_345-h-19.htm.xhtml',
            '2903486949112998543_345-h-20.htm.xhtml', '2903486949112998543_345-h-21.htm.xhtml',
            '2903486949112998543_345-h-22.htm.xhtml', '2903486949112998543_345-h-23.htm.xhtml',
            '2903486949112998543_345-h-24.htm.xhtml', '2903486949112998543_345-h-25.htm.xhtml',
            '2903486949112998543_345-h-26.htm.xhtml', '2903486949112998543_345-h-27.htm.xhtml',
            '2903486949112998543_345-h-28.htm.xhtml', '2903486949112998543_345-h-29.htm.xhtml',
            '2903486949112998543_345-h-30.htm.xhtml', '2903486949112998543_345-h-31.htm.xhtml',
            'toc.xhtml',
        ])


if __name__ == '__main__':
    unittest.main()
