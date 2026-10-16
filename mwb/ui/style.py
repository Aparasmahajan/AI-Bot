"""The look of MWB's own windows (setup, settings): the demo's light theme on Tkinter's clam theme, as the API key
window first set it, so they look like one product."""
from tkinter import ttk

from mwb.ui.api_key import (AMBER, AMBER_WASH, COBALT, COBALT_DARK, COBALT_SOFT, FADED, FONT, INK, INK_2, INK_3, OK,
                            OK_WASH, PAPER, RULE, SHEET, SIGNAL, _icon as icon, _prepare_process as prepare)

__all__ = ['AMBER', 'AMBER_WASH', 'COBALT', 'FONT', 'INK', 'INK_2', 'INK_3', 'OK', 'OK_WASH', 'PAPER', 'RULE',
           'SHEET', 'SIGNAL', 'apply', 'prepare', 'place']


def apply(root, title):
    """Style the window and return px(n), which scales a size for the display."""
    scale = root.winfo_fpixels('1i') / 96
    px = lambda n: round(n * scale)
    root.title(title)
    root.configure(bg=SHEET)
    root._mwb_icons = (icon(px(32)), icon(px(16)))
    root.iconphoto(True, *root._mwb_icons)
    s = ttk.Style(root)
    s.theme_use('clam')
    s.configure('.', background=SHEET, foreground=INK, font=(FONT, 10))
    s.configure('Title.TLabel', font=(FONT + ' Semibold', 15))
    s.configure('Head.TLabel', font=(FONT + ' Semibold', 11))
    s.configure('Sub.TLabel', foreground=INK_2)
    s.configure('Small.TLabel', foreground=INK_3, font=(FONT, 9))
    s.configure('Warn.TLabel', foreground=AMBER, font=(FONT, 9))
    s.configure('Good.TLabel', foreground=OK, font=(FONT, 9))
    s.configure('Bad.TLabel', foreground=SIGNAL, font=(FONT, 9))
    s.configure('Paper.TFrame', background=PAPER)
    s.configure('Paper.TLabel', background=PAPER, foreground=INK_2)
    s.configure('PaperHead.TLabel', background=PAPER, foreground=INK_3, font=(FONT, 9, 'bold'))
    s.configure('TSeparator', background=RULE)
    s.configure('TEntry', fieldbackground=SHEET, foreground=INK, insertcolor=INK, bordercolor=RULE, lightcolor=SHEET,
                darkcolor=SHEET, padding=(px(6), px(4)))
    s.map('TEntry', bordercolor=[('focus', COBALT)], lightcolor=[('focus', COBALT)])
    s.configure('TCombobox', fieldbackground=SHEET, background=SHEET, foreground=INK, bordercolor=RULE,
                arrowcolor=INK_2, padding=(px(6), px(3)))
    s.map('TCombobox', fieldbackground=[('readonly', SHEET)], bordercolor=[('focus', COBALT)])
    for w in ('TCheckbutton', 'TRadiobutton'):
        s.configure(w, foreground=INK, indicatorbackground=SHEET, indicatorforeground=COBALT, upperbordercolor=RULE,
                    lowerbordercolor=RULE)
        s.map(w, background=[('active', SHEET)], foreground=[('disabled', FADED)],
              indicatorbackground=[('pressed', PAPER), ('disabled', PAPER)])
    s.configure('TButton', padding=(px(14), px(5)), background=SHEET, foreground=INK, bordercolor=RULE,
                lightcolor=SHEET, darkcolor=SHEET, focuscolor=COBALT_SOFT)
    hover = [('disabled', SHEET), ('pressed', PAPER), ('active', PAPER)]
    s.map('TButton', background=hover, lightcolor=hover, darkcolor=hover, foreground=[('disabled', FADED)],
          bordercolor=[('focus', COBALT)])
    s.configure('Primary.TButton', background=COBALT, foreground='#FFFFFF', bordercolor=COBALT, lightcolor=COBALT,
                darkcolor=COBALT, focuscolor='#FFFFFF')
    fill = [('disabled', COBALT_SOFT), ('pressed', COBALT_DARK), ('active', COBALT_DARK)]
    s.map('Primary.TButton', background=fill, bordercolor=fill, lightcolor=fill, darkcolor=fill,
          foreground=[('disabled', '#FFFFFF')])
    s.configure('TNotebook', background=SHEET, bordercolor=RULE, tabmargins=(px(2), px(4), px(2), 0))
    s.configure('TNotebook.Tab', background=PAPER, foreground=INK_2, bordercolor=RULE, padding=(px(12), px(5)))
    s.map('TNotebook.Tab', background=[('selected', SHEET)], foreground=[('selected', INK)])
    return px


def place(root):
    """Centre the window, a little above the middle, and bring it to the front."""
    import ctypes
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    area = (ctypes.c_long * 4)()
    ctypes.windll.user32.SystemParametersInfoW(0x30, 0, area, 0)            # the work area: above the taskbar
    top, bottom = area[1], area[3] or root.winfo_screenheight()
    x = (root.winfo_screenwidth() - w) // 2
    root.geometry(f'+{x}+{top}')
    root.update()
    r = (ctypes.c_long * 4)()                                               # the whole window, title bar included
    ctypes.windll.user32.GetWindowRect(int(root.wm_frame(), 16), r)
    outer = r[3] - r[1] or h
    y = max(top, min(top + (bottom - top - outer) // 3, bottom - outer - 8))
    root.geometry(f'+{x}+{y}')
    root.lift()
    root.attributes('-topmost', True)
    root.after(400, lambda: root.attributes('-topmost', False))
    root.focus_force()
