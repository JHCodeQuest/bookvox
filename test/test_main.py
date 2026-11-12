import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # lets the tests run from the repo root too
from epub_factory import build_epub

from ebooklib import epub

from bookvox.core import find_document_chapters_and_extract_texts, main

REPO = Path(__file__).resolve().parent.parent


def optional_book(name):
    """Skip cleanly when a real book is not in the repo: the epubs under epub/ are not committed."""
    path = REPO / 'epub' / f'{name}.epub'
    return unittest.skipUnless(path.exists(), f'optional book epub/{name}.epub is not in the repo; '
                                              f'place it there to run this test')


LONG_ITALIAN = (
    'È vero che non ho mai saputo troppo bene quante camere, quanti atri, quante scale e quanti corridoi '
    'avesse e molte volte, dirigendomi verso la mia camera da letto, mi sono ritrovato in saloni o in '
    'bagni non solo totalmente sconosciuti, come se fossero spariti i muri tra la mia casa e un’altra a '
    'essa appiccicata, ma anche lontani nel tempo, nello spazio e nel ricordo, con mobili scintillanti e '
    'strani, con orologi a pendolo di noce e candelabri con piccole foglie di ottone, ma questa volta la '
    'mia casa buia, dalle cui finestre nevicava all’impazzata, mi è parsa sconfinata.')


def m4b_chapters(path):
    """The audio duration in seconds and the chapter titles, as ffprobe reports them."""
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_chapters', '-show_entries', 'format=duration', '-of', 'json', str(path)],
        capture_output=True, text=True, encoding='utf-8', check=True).stdout
    data = json.loads(out)
    return float(data['format']['duration']), [c['tags']['title'] for c in data['chapters']]


@unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg not installed')
class MainTest(unittest.TestCase):
    def setUp(self):
        # rmtree(ignore_errors): ebooklib's read_epub leaves the zip open, which Windows forbids deleting.
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def convert(self, documents, book_name='book', select=None, **kwargs):
        epub_path = self.tmp / f'{book_name}.epub'
        build_epub(epub_path, documents)
        merged = dict(voice='af_sky', pick_manually=False, speed=1.0,
                      max_chapters=1, max_sentences=2, output_folder=str(self.tmp))
        if select is not None:
            merged['selected_chapters'] = [
                c for c in find_document_chapters_and_extract_texts(epub.read_epub(str(epub_path)))
                if c.get_name() in select]
        merged.update(kwargs)
        main(str(epub_path), **merged)
        m4b_file = self.tmp / f'{book_name}.m4b'
        self.assertTrue(m4b_file.exists())
        self.assertTrue(m4b_file.stat().st_size > 1024)
        # the file contains audio and one m4b chapter per converted chapter
        # (no TOC in the synthetic book, so create_index_file falls back to 'Chapter N')
        duration, titles = m4b_chapters(m4b_file)
        self.assertGreater(duration, 0)
        self.assertEqual(titles, ['Chapter 1'])
        return merged['selected_chapters'] if select is not None else None

    def test_conversion_with_spaces_in_filename_and_selected_chapters(self):
        # default-voice auto-selection conversions are covered by test_cli.test_epub on mini.epub
        selected = self.convert([
            ('ch01.xhtml', 'It was a dark and stormy night. ' * 5),
            ('ch02.xhtml', 'Suddenly, a shot rang out. ' * 5),
        ], book_name='pirandello e spazio', select=['ch02.xhtml'])
        self.assertEqual([c.get_name() for c in selected], ['ch02.xhtml'])
        # only the explicitly selected chapter was synthesized
        self.assertTrue((self.tmp / 'pirandello e spazio_chapter_1_af_sky_ch02.xhtml.wav').exists())
        self.assertFalse((self.tmp / 'pirandello e spazio_chapter_1_af_sky_ch01.xhtml.wav').exists())

    def test_conversion_with_espeak_voice_and_long_sentence(self):
        # Spanish routes through eSpeak, and a 400+ chars sentence exercises the sentence splitter.
        self.convert([('ch01.xhtml', LONG_ITALIAN)], voice='ef_dora', max_sentences=1)

    def convert_real_book(self, name, **kwargs):
        epub_path = REPO / 'epub' / f'{name}.epub'
        merged = dict(voice='af_sky', pick_manually=False, speed=1.0,
                      max_chapters=1, max_sentences=2, output_folder=str(self.tmp))
        merged.update(kwargs)
        main(str(epub_path), **merged)
        m4b_file = self.tmp / f'{name}.m4b'
        self.assertTrue(m4b_file.exists())
        self.assertTrue(m4b_file.stat().st_size > 1024)

    # The tests below need real books that are not committed (copyright); they are skipped when absent.
    # They cover non-English G2P routes that synthetic tests cannot.

    @optional_book('manzoni')
    def test_italian_manzoni(self):
        self.convert_real_book('manzoni', voice='im_nicola')

    @optional_book('baudelaire')
    def test_french_baudelaire(self):
        self.convert_real_book('baudelaire', voice='ff_siwis')

    @optional_book('chinese')
    def test_chinese(self):
        self.convert_real_book('chinese', voice='zf_xiaobei')


if __name__ == '__main__':
    unittest.main()
