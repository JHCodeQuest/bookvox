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
