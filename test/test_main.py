import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

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


class AudioReuseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.path = self.tmp / 'book.epub'
        build_epub(self.path, [('ch01.xhtml', 'Original chapter text. ' * 10)])
        self.chapter = epub.EpubHtml(title='Chapter', file_name='ch01.xhtml')
        self.chapter.extracted_text = 'Original chapter text. ' * 10
        self.chapter.chapter_index = 0
        for name in ('load_spacy', 'set_espeak_library', 'KPipeline', 'create_index_file', 'create_m4b'):
            mocker = patch(f'bookvox.core.{name}')
            mocker.start()
            self.addCleanup(mocker.stop)
        mocker = patch('bookvox.core.gen_audio_segments', return_value=[np.zeros(2400)])
        self.generate = mocker.start()
        self.addCleanup(mocker.stop)
        self.wav = self.tmp / 'book_chapter_1_af_sky_ch01.xhtml.wav'
        self.fingerprint = self.wav.with_suffix('.wav.sha256')
        chapter2 = epub.EpubHtml(title='Chapter 2', file_name='ch02.xhtml')
        chapter2.extracted_text = 'Second chapter text. ' * 10
        chapter2.chapter_index = 1
        self.chapter2 = chapter2
        self.wav2 = self.tmp / 'book_chapter_2_af_sky_ch02.xhtml.wav'

    def convert(self, **kwargs):
        args = dict(file_path=str(self.path), voice='af_sky', pick_manually=False, speed=1.0,
                    output_folder=str(self.tmp), selected_chapters=[self.chapter])
        args.update(kwargs)
        main(**args)

    def test_matching_inputs_reuse_audio(self):
        self.convert()
        self.convert()
        self.assertEqual(self.generate.call_count, 1)

    def test_partial_reuse_run_reaches_100_percent(self):
        def account_sentences(pipeline, text, voice, speed, stats=None,
                              max_sentences=None, post_event=None):
            # mimic gen_audio_segments' accounting: the chunks partition text exactly,
            # like spaCy sentences do, so processed sums to len(text)
            for i in range(0, len(text), 100):
                if stats:
                    stats.processed_chars += len(text[i:i + 100])
                    stats.progress = min(100, stats.processed_chars * 100 // stats.total_chars)
                    if post_event:
                        post_event('CORE_PROGRESS', stats=stats)
            return [np.zeros(2400)]

        self.generate.side_effect = account_sentences
        self.convert(selected_chapters=[self.chapter, self.chapter2])
        self.assertTrue(self.wav2.exists())
        self.wav2.unlink()  # run 2 must reuse chapter 1 but re-synthesize chapter 2
        self.generate.reset_mock()
        events = []
        self.convert(selected_chapters=[self.chapter, self.chapter2],
                     post_event=lambda name, **kw: events.append((name, kw)))

        progress = [kw['stats'].progress for name, kw in events if name == 'CORE_PROGRESS']
        self.assertTrue(progress, 'no CORE_PROGRESS events: chapter 2 was not re-synthesized')
        # the first progress already includes chapter 1's reused chars: the reuse `continue`
        # added len(chapter.extracted_text) without any synthesis (processed >= 230 here)
        first = next(kw['stats'] for name, kw in events if name == 'CORE_PROGRESS')
        self.assertGreaterEqual(first.processed_chars, len(self.chapter.extracted_text))
        # the intro is in neither total nor processed on a reused-chapter-1 run: it was
        # never narrated, so the denominator is exactly the two chapters' text
        stats = [kw['stats'] for name, kw in events if name == 'CORE_PROGRESS'][-1]
        self.assertEqual(stats.total_chars,
                         len(self.chapter.extracted_text) + len(self.chapter2.extracted_text))  # 440, not 455
        self.assertEqual(stats.processed_chars, stats.total_chars)
        self.assertEqual(progress[-1], 100)  # an intro-in-total regression would end at 96 and stall the bar
        self.assertEqual(self.generate.call_count, 1)  # only chapter 2 was synthesized
        self.assertEqual(self.generate.call_args.args[1], self.chapter2.extracted_text)  # no intro prefix

    def test_changed_speed_or_sentence_limit_regenerates_audio(self):
        for changed in ({'speed': 1.5}, {'max_sentences': 1}):
            with self.subTest(changed=changed):
                self.convert()
                self.generate.reset_mock()
                self.convert(**changed)
                self.generate.assert_called_once()

    def test_gui_edited_text_regenerates_audio(self):
        self.convert()
        self.chapter.extracted_text = 'Edited chapter text. ' * 10
        self.convert()
        self.assertEqual(self.generate.call_count, 2)
        self.assertIn(self.chapter.extracted_text, self.generate.call_args.args[1])

    def test_changed_intro_regenerates_audio(self):
        self.convert()
        book = epub.read_epub(str(self.path))
        book.add_author('New Author')
        with patch('bookvox.core.epub.read_epub', return_value=book):
            self.convert()
        self.assertEqual(self.generate.call_count, 2)

    def test_legacy_or_missing_or_invalid_sidecar_regenerates_audio(self):
        self.wav.write_bytes(b'legacy audio')
        self.convert()
        for content in (None, b'wrong hash', b'\xff'):
            with self.subTest(content=content):
                if content is None:
                    self.fingerprint.unlink()
                else:
                    self.fingerprint.write_bytes(content)
                self.generate.reset_mock()
                self.convert()
                self.generate.assert_called_once()

    def test_missing_wav_regenerates_audio(self):
        self.convert()
        self.wav.unlink()
        self.convert()
        self.assertEqual(self.generate.call_count, 2)

    def test_changed_voice_generates_new_audio(self):
        self.convert()
        self.convert(voice='af_heart')
        self.assertEqual(self.generate.call_count, 2)

    def test_changed_sample_rate_regenerates_audio(self):
        self.convert()
        with patch('bookvox.core.sample_rate', 16000):
            self.convert()
        self.assertEqual(self.generate.call_count, 2)

    def test_failed_write_invalidates_previous_fingerprint(self):
        self.convert()
        with patch('bookvox.core.soundfile.write', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.convert(speed=1.5)
        self.assertFalse(self.fingerprint.exists())
        self.convert()
        self.assertEqual(self.generate.call_count, 3)

    def test_empty_edited_chapter_does_not_reuse_old_audio(self):
        self.convert()
        self.chapter.extracted_text = ''
        with patch('bookvox.core.create_m4b') as export:
            self.convert()
        self.assertEqual(export.call_args.args[0], [])


if __name__ == '__main__':
    unittest.main()
