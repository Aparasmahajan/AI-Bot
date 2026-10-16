"""Pasting (mwb/insert.py) into a small test window of its own, never into your apps. It opens for about two
seconds and is skipped when Windows won't bring it to the front (for example while you're typing elsewhere).

Checks: the text arrives; your clipboard comes back afterwards; MWB's text is kept out of clipboard history;
typing works for the type-instead list."""
import ctypes, threading, time, tkinter as tk, unittest

from mwb import insert, winapi


class PasteWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.users_clipboard = winapi.clipboard_get()          # yours, put back at the end

    @classmethod
    def tearDownClass(cls):
        if cls.users_clipboard is not None:
            winapi.clipboard_set(cls.users_clipboard)

    def setUp(self):
        self.root = tk.Tk()
        self.root.title('MWB paste test')
        self.root.geometry('420x120+40+40')
        self.root.attributes('-topmost', True)
        self.text = tk.Text(self.root)
        self.text.pack(fill='both', expand=True)
        self.root.update()
        hwnd = int(self.root.wm_frame(), 16)
        winapi.send_keys((winapi.VK_MENU, False), (winapi.VK_MENU, True))   # lets this process take the foreground
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        self.root.focus_force()
        self.text.focus_set()
        for _ in range(20):
            self.root.update()
            time.sleep(0.02)
        self.hwnd = hwnd
        if winapi.user32.GetForegroundWindow() != hwnd:
            self.root.destroy()
            self.skipTest('the test window could not come to the front')

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run_insert(self, **kw):
        if winapi.user32.GetForegroundWindow() != self.hwnd:
            self.skipTest('the test window lost the front')
        result = {}
        t = threading.Thread(target=lambda: result.update(how=insert.insert(**kw)))
        t.start()
        while t.is_alive():                 # keep Tk's loop turning so the paste is received
            self.root.update()
            time.sleep(0.01)
        for _ in range(10):
            self.root.update()
            time.sleep(0.01)
        got = self.text.get('1.0', 'end-1c')
        if not got and winapi.user32.GetForegroundWindow() != self.hwnd:
            self.skipTest('another window took the front during the paste')
        return result['how'], got

    def test_paste_and_clipboard_restored(self):
        winapi.clipboard_set('your own clipboard text')
        how, got = self.run_insert(text='Ship it today. Ask Priya.\nThanks ', restore_ms=300)
        self.assertEqual(how, 'paste')
        self.assertEqual(got, 'Ship it today. Ask Priya.\nThanks ')
        self.assertEqual(winapi.clipboard_get(), 'your own clipboard text')

    def test_kept_out_of_clipboard_history(self):
        winapi.clipboard_set('MWB text', private=True)
        fmt = winapi.user32.RegisterClipboardFormatW('CanIncludeInClipboardHistory')
        self.assertTrue(winapi.user32.IsClipboardFormatAvailable(fmt))
        winapi.clipboard_set('')

    def test_type_instead(self):
        how, got = self.run_insert(text='Typed: naïve café ✓', type_instead=['python.exe', 'pythonw.exe'],
                                   app='python.exe')
        self.assertEqual(how, 'type')
        self.assertEqual(got, 'Typed: naïve café ✓')


if __name__ == '__main__':
    unittest.main()
