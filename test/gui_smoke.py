"""Smoke test for the wxPython GUI. It drives the real window handlers without showing the window.

Needs wxPython, ffmpeg and the Kokoro model (a real conversion runs), so it is not named test_*.py and
is not picked up by `python -m unittest`. Run it by hand:

    pip install bookvox wxpython        # or: pip install . wxpython
    python test/gui_smoke.py [path/to/book.epub]

It checks that the window builds, that a failing conversion unlocks the window and shows an error
(the CORE_FAILED path), and that a good conversion produces an m4b and finishes. Exit code 1 on any failure.
"""
import shutil, sys, tempfile, time, traceback
from pathlib import Path

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / 'epub' / 'mini.epub'
WAIT = 420  # seconds to wait for a conversion to report back
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print(('PASS ' if ok else 'FAIL ') + name + (f'   [{detail}]' if detail else ''), flush=True)


import wx

dialogs = []
wx.MessageBox = lambda *a, **k: (dialogs.append(a), wx.OK)[1]  # record dialogs instead of blocking on them

from bookvox import ui

app = wx.App(False)
frame = ui.MainWindow(None, 'smoke test')  # never shown
app.SetTopWindow(frame)
check('main window constructs (wxPython %s)' % wx.version().split()[0], True)

opened_folders = []
frame.open_folder_with_explorer = lambda p: opened_folders.append(p)  # do not open Explorer
work = Path(tempfile.mkdtemp())


def pump(cond, timeout):
    end = time.time() + timeout
    while time.time() < end:
        wx.Yield()
        if cond():
            return True
        time.sleep(0.05)
    return False


def run_case(label, break_book):
    book = work / (label + '.epub')
    shutil.copy(SRC, book)
    out = work / ('out_' + label)
    frame.open_epub(str(book))  # creates the layout, including the output folder field
    frame.output_folder_text_ctrl.SetValue(str(out))
    check(label + ': book loads into the window', len(frame.document_chapters) >= 2)
    if break_book:
        book.unlink()  # core.main re-reads the file in its thread, so this makes the conversion fail
    d0, o0 = len(dialogs), len(opened_folders)
    frame.on_start(None)
    check(label + ': Start locks the window while running', frame.synthesis_in_progress and not frame.start_button.IsEnabled())
    check(label + ': an outcome event reached the window', pump(lambda: len(dialogs) > d0 or len(opened_folders) > o0, WAIT))
    return out, d0, o0


try:
    out, d0, o0 = run_case('broken', break_book=True)
    check('broken: an error dialog names the problem', len(dialogs) > d0 and 'synthesis failed' in str(dialogs[-1][0]))
    check('broken: window unlocked again', frame.synthesis_in_progress is False
          and frame.start_button.IsEnabled() and frame.params_panel.IsEnabled())
    check('broken: not reported as finished', len(opened_folders) == o0)
except Exception:
    traceback.print_exc()
    check('failure path ran without a harness error', False)

try:
    out, d0, o0 = run_case('good', break_book=False)
    check('good: m4b produced', bool(list(out.glob('*.m4b'))))
    check('good: finished, output folder opened, window unlocked, no error dialog',
          len(opened_folders) > o0 and frame.synthesis_in_progress is False and len(dialogs) == d0)
except Exception:
    traceback.print_exc()
    check('success path ran without a harness error', False)

failed = [n for n, ok in results if not ok]
print('SUMMARY: %d passed, %d failed' % (len(results) - len(failed), len(failed)), flush=True)
sys.exit(1 if failed else 0)
