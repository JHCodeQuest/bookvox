import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

REPO = Path(__file__).resolve().parent.parent
MINI_EPUB = REPO / 'epub' / 'mini.epub'


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def cli(self, *args):
        """Run the CLI inside a temporary folder, so output files never land in the repo."""
        env = {**os.environ, 'PYTHONPATH': str(REPO), 'PYTHONIOENCODING': 'utf-8'}
        result = subprocess.run(
            [sys.executable, '-m', 'bookvox.cli', *map(str, args)],
            cwd=self.tmp, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        return result.stdout

    def test_help(self):
        out = self.cli('--help')
        self.assertIn('af_sky', out)
        self.assertIn('usage:', out)

    def test_epub(self):
        out = self.cli(MINI_EPUB)
        self.assertIn('Found cover image', out)
        self.assertIn('Creating M4B file', out)
        self.assertTrue((self.tmp / 'mini.m4b').exists())
        self.assertTrue((self.tmp / 'mini.m4b').stat().st_size > 256 * 1024)
        self.assertEqual(self.chapter_titles(self.tmp / 'mini.m4b'), ['Chapter One', 'Chapter Two'])

    def chapter_titles(self, m4b):
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_chapters', '-of', 'json', str(m4b)],
                               capture_output=True, text=True, encoding='utf-8', check=True)
        return [chapter['tags']['title'] for chapter in json.loads(probe.stdout)['chapters']]

    def test_epub_voice_and_output_folder(self):
        out = self.cli(MINI_EPUB, '-v', 'af_sky', '-o', 'out/sub')  # relative to the temporary folder
        self.assertIn('Found cover image', out)
        self.assertIn('Creating M4B file', out)
        self.assertTrue((self.tmp / 'out' / 'sub' / 'mini.m4b').exists())
        self.assertTrue((self.tmp / 'out' / 'sub' / 'mini.m4b').stat().st_size > 256 * 1024)

    @unittest.skip('Not implemented yet')
    def test_md(self):
        content = (
            '## Italy\n'
            'Italy, officially the Italian Republic, is a country in '
            '(Southern)[https://en.wikipedia.org/wiki/Southern_Europe] and Western Europe. '
            'It consists of a peninsula that extends into the Mediterranean Sea, '
            'with the Alps on its northern land border, '
            'as well as nearly 800 islands, notably Sicily and Sardinia.')
        file_name = NamedTemporaryFile('w', suffix='.txt', delete=False).write(content)
        out = self.cli(file_name)
        self.assertIn('Creating M4B file', out)
        self.assertTrue(Path(file_name).exists())
        self.assertTrue(Path('file_name').stat().st_size > 256 * 1024)

    @unittest.skip('Not implemented yet')
    def test_txt(self):
        content = (
            'Italy, officially the Italian Republic, is a country in Southern and Western Europe. '
            'It consists of a peninsula that extends into the Mediterranean Sea, '
            'with the Alps on its northern land border, '
            'as well as nearly 800 islands, notably Sicily and Sardinia.')
        file_name = NamedTemporaryFile('w', suffix='.txt', delete=False).write(content)
        out = self.cli(file_name)
        self.assertIn('Creating M4B file', out)
        self.assertTrue(Path('text.mp4').exists())
        self.assertTrue(Path('text.mp4').stat().st_size > 256 * 1024)
