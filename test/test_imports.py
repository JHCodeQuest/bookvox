import ast
import unittest
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent / 'bookvox'
SIBLING_MODULES = {p.stem for p in PACKAGE_DIR.glob('*.py')} - {'__init__'}


class ImportsTest(unittest.TestCase):
    def test_no_bare_imports_of_sibling_modules(self):
        """`import core` only works through a sys.path hack in __init__.py and loads a second copy of the module."""
        bare = []
        for path in sorted(PACKAGE_DIR.glob('*.py')):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                else:
                    continue
                bare += [f'{path.name}:{node.lineno} imports {n}' for n in names if n.split('.')[0] in SIBLING_MODULES]
        self.assertEqual(bare, [])

    def test_no_deprecated_wx_calls(self):
        """These wx names are deprecated and will be removed from wxPython; each has a plain replacement."""
        deprecated = {'EmptyImage': 'wx.Image(w, h)', 'EmptyBitmap': 'wx.Bitmap(w, h)', 'EmptyIcon': 'wx.Icon()',
                      'BitmapFromImage': 'wx.Bitmap(image)', 'ImageFromBitmap': 'bitmap.ConvertToImage()'}
        found = []
        for path in sorted(PACKAGE_DIR.glob('*.py')):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                        and node.value.id == 'wx' and node.attr in deprecated):
                    found.append(f'{path.name}:{node.lineno} uses wx.{node.attr}, use {deprecated[node.attr]}')
        self.assertEqual(found, [])
