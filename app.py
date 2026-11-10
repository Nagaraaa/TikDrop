"""French desktop interface for TikDrop (MIT)."""
import functools
from importlib import metadata
import json
import logging
import logging.handlers
import os
from pathlib import Path
import platform
import queue
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlsplit
from core import scan_links, worker

VERSION = '1.1.0'
C = {
    'bg': '#0c0f16', 'surface': '#141923', 'raised': '#1b2130', 'line': '#262e3f',
    'hover': '#252d3f', 'text': '#eef2fa', 'muted': '#8f9ab0', 'faint': '#5e687c',
    'accent': '#25d9b8', 'accent_hi': '#5cebd1', 'ink': '#04211c', 'select': '#1f4a44',
    'ok': '#25d9b8', 'bad': '#ff5c7a', 'warn': '#f2b84b', 'banner': '#10302b',
}
WIN = sys.platform == 'win32'


# ---------------------------------------------------------------- helpers

def settings_path():
    base = os.environ.get('APPDATA') or str(Path.home() / '.config')
    return Path(base) / 'TikDrop' / 'settings.json'


def load_settings():
    try:
        data = json.loads(settings_path().read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError:
        pass


@functools.lru_cache(maxsize=None)
def engine_version():
    try:
        return metadata.version('yt-dlp')
    except metadata.PackageNotFoundError:
        return 'inconnue'


def error_report(url, message, detail=''):
    """Plain-text summary of a failure, ready to paste into a bug report."""
    lines = [f'TikDrop {VERSION} · yt-dlp {engine_version()} · {platform.platform()}',
             f'Lien : {url}', f'Erreur : {message}']
    if detail and detail.strip() != message:
        lines.append('Détail : ' + detail.strip())
    return '\n'.join(lines)


@functools.lru_cache(maxsize=None)
def failure_log():
    """Logger writing failures to tikdrop.log next to settings.json (2 × 256 Ko max)."""
    logger = logging.getLogger('tikdrop')
    logger.propagate = False
    try:
        path = settings_path().with_name('tikdrop.log')
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(path, maxBytes=256_000, backupCount=1, encoding='utf-8')
        handler.setFormatter(logging.Formatter('--- %(asctime)s\n%(message)s'))
    except OSError:
        handler = logging.NullHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def run_worker(cmd, emit, on_start=lambda proc: None):
    """Run one worker process and forward its JSON events to ``emit``.

    Returns True when a file was saved. A worker that stops without reporting
    an error (crash, missing file in the build…) gets one built from its exit
    code and whatever it printed, so the reason is never lost.
    """
    done = reported = False
    other = []
    proc = subprocess.Popen(
        cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace',
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    on_start(proc)
    with proc.stdout:
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                event = None
            if isinstance(event, dict):
                done |= event.get('type') == 'done'
                reported |= event.get('type') == 'error'
                emit(event)
            elif line.strip():
                other.append(line.rstrip())
    code = proc.wait()
    ok = code == 0 and done
    if not ok and not reported:
        emit({'type': 'error', 'message': 'Le téléchargement n’a pas abouti.',
              'detail': '\n'.join([f'Code de sortie : {code}'] + other[-20:])})
    return ok


def fr_number(value, digits=1):
    return f'{value:.{digits}f}'.replace('.', ',')


def human_size(n):
    n = float(n or 0)
    for unit in ('o', 'Ko', 'Mo'):
        if n < 1024:
            return f'{n:.0f} {unit}' if unit == 'o' else f'{fr_number(n)} {unit}'
        n /= 1024
    return f'{fr_number(n)} Go'


def human_eta(seconds):
    if seconds is None:
        return ''
    seconds = int(seconds)
    return f'{seconds} s' if seconds < 60 else f'{seconds // 60} min {seconds % 60:02d} s'


def plural(n, word):
    return f'{n} {word}{"s" if n > 1 else ""}'


def describe_link(url):
    """Title and subtitle shown for a link before its metadata is known."""
    parts = urlsplit(url)
    segments = [s for s in parts.path.split('/') if s]
    if segments and segments[0].startswith('@'):
        return segments[0], 'Vidéo ' + segments[-1]
    return 'Lien de partage', f'{parts.hostname}/{"/".join(segments)}'


def shorten(text, limit):
    text = ' '.join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = (x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1)
    return canvas.create_polygon(pts, smooth=True, **kw)


def make_icon(master, size):
    """TikDrop logo (rounded teal tile with a download arrow) drawn pixel by pixel."""
    img = tk.PhotoImage(master=master, width=size, height=size)
    s = size / 64
    lo, hi, r = 2 * s, 62 * s, 15 * s

    def put(color, x1, x2, y):
        x1, x2 = max(0, int(round(x1))), min(size, int(round(x2)))
        if x2 > x1:
            img.put(color, to=(x1, y, x2, y + 1))

    for y in range(size):
        cy = y + 0.5
        if not lo <= cy <= hi:
            continue
        dy = max(lo + r - cy, cy - (hi - r), 0)
        dx = (r * r - dy * dy) ** 0.5 if dy else r
        put(C['accent'], lo + r - dx, hi - r + dx, y)
        if 12 * s <= cy <= 31 * s:                      # shaft
            put(C['ink'], 27.5 * s, 36.5 * s, y)
        if 27 * s <= cy <= 45 * s:                      # arrow head
            half = 45 * s - cy
            put(C['ink'], 32 * s - half, 32 * s + half, y)
        if 48 * s <= cy <= 53.5 * s:                    # tray
            put(C['ink'], 16 * s, 48 * s, y)
    return img


# ---------------------------------------------------------------- widgets

class Button(tk.Canvas):
    """Flat rounded button drawn on a canvas (hover, focus and disabled states)."""
    KINDS = {  # normal, hover, text, disabled fill, disabled text, outline
        'primary': (C['accent'], C['accent_hi'], C['ink'], '#1a3a36', '#4f7d76', ''),
        'secondary': (C['raised'], C['hover'], C['text'], C['raised'], C['faint'], C['line']),
        'ghost': (None, C['hover'], C['muted'], None, C['faint'], ''),
        'danger': (C['raised'], '#3a1f29', C['bad'], C['raised'], C['faint'], C['line']),
    }

    def __init__(self, master, app, text, command, kind='secondary', small=False):
        self.app, self.command, self.kind, self.small = app, command, kind, small
        self.parent_bg = master.cget('bg')
        self.enabled, self.hover, self.focused = True, False, False
        super().__init__(master, highlightthickness=0, bd=0, bg=self.parent_bg,
                         cursor='hand2', takefocus=1)
        self.font = app.f_btn_bold if kind == 'primary' else app.f_btn
        self.bind('<Enter>', lambda e: self._set(hover=True))
        self.bind('<Leave>', lambda e: self._set(hover=False))
        self.bind('<FocusIn>', lambda e: self._set(focused=True))
        self.bind('<FocusOut>', lambda e: self._set(focused=False))
        self.bind('<ButtonRelease-1>', self._click)
        self.bind('<Return>', lambda e: self._click())
        self.bind('<space>', lambda e: self._click())
        self.set_text(text)

    def set_text(self, text):
        self.text = text
        pad = self.app.px(12 if self.small else 20)
        self.configure(width=self.font.measure(text) + 2 * pad,
                       height=self.app.px(30 if self.small else 40))
        self.redraw()

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.configure(cursor='hand2' if enabled else 'arrow', takefocus=1 if enabled else 0)
        self.redraw()

    def _set(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)
        self.redraw()

    def _click(self, event=None):
        inside = event is None or (0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height())
        if self.enabled and inside:
            self.command()

    def redraw(self):
        self.delete('all')
        w, h = int(self['width']), int(self['height'])
        bg, hover, fg, dis_bg, dis_fg, outline = self.KINDS[self.kind]
        fill = (hover if self.hover else bg) if self.enabled else dis_bg
        if self.focused and self.enabled:
            outline = C['accent'] if self.kind != 'primary' else C['text']
        round_rect(self, 1, 1, w - 1, h - 1, self.app.px(8),
                   fill=fill or self.parent_bg, outline=outline or fill or self.parent_bg)
        self.create_text(w / 2, h / 2, text=self.text, font=self.font,
                         fill=fg if self.enabled else dis_fg)


class ProgressLine(tk.Canvas):
    def __init__(self, master, app, height=4, trough=None):
        super().__init__(master, height=app.px(height), bg=master.cget('bg'),
                         highlightthickness=0, bd=0)
        self.value, self.color, self.trough = 0.0, C['accent'], trough or C['line']
        self.bind('<Configure>', lambda e: self.redraw())

    def set(self, value, color=None):
        self.value = max(0.0, min(1.0, value))
        self.color = color or self.color
        self.redraw()

    def redraw(self):
        self.delete('all')
        w, h = self.winfo_width(), int(self['height'])
        if w <= 1:
            return
        self.create_rectangle(0, 0, w, h, fill=self.trough, width=0)
        if self.value > 0:
            self.create_rectangle(0, 0, max(2, w * self.value), h, fill=self.color, width=0)


class Row(tk.Frame):
    """One video in the download queue."""

    def __init__(self, master, app, url):
        super().__init__(master, bg=C['surface'])
        self.app, self.url = app, url
        self.state, self.path, self.error, self.detail = 'waiting', None, '', ''
        px = app.px
        self.columnconfigure(1, weight=1)
        self.dot = tk.Canvas(self, width=px(10), height=px(10), bg=C['surface'], highlightthickness=0)
        self.dot.grid(row=0, column=0, padx=(px(18), px(12)), pady=(px(15), 0), sticky='n')
        head, sub = describe_link(url)
        self.title = tk.Label(self, text=head, font=app.f_bold, fg=C['text'], bg=C['surface'], anchor='w')
        self.title.grid(row=0, column=1, sticky='ew', pady=(px(10), 0))
        self.sub = tk.Label(self, text=sub, font=app.f_small, fg=C['muted'], bg=C['surface'],
                            anchor='w', justify='left')
        self.sub.grid(row=1, column=1, sticky='ew')
        self.badge = tk.Label(self, text='En attente', font=app.f_small_bold, fg=C['faint'],
                              bg=C['surface'], anchor='e')
        self.badge.grid(row=0, column=2, sticky='e', padx=(px(12), px(18)), pady=(px(10), 0))
        self.action = Button(self, app, 'Afficher', self.reveal, kind='ghost', small=True)
        self.copy_btn = Button(self, app, 'Copier l’erreur', self.copy_error, kind='ghost', small=True)
        self.bar = ProgressLine(self, app, height=3)
        self.bar.grid(row=2, column=1, columnspan=2, sticky='ew', padx=(0, px(18)), pady=(px(8), 0))
        self.bar.grid_remove()
        tk.Frame(self, bg=C['line'], height=1).grid(row=3, column=0, columnspan=3, sticky='ew', pady=(px(10), 0))
        self.bind('<Configure>', lambda e: self.sub.configure(wraplength=max(px(160), e.width - px(190))))
        self._dot(C['faint'])

    def _dot(self, color):
        self.dot.delete('all')
        self.dot.create_oval(1, 1, self.app.px(10) - 1, self.app.px(10) - 1, fill=color, width=0)

    def _badge(self, text, color):
        self.badge.configure(text=text, fg=color)

    def begin(self):
        self.state = 'active'
        self._dot(C['accent'])
        self._badge('Connexion…', C['accent'])
        self.bar.set(0, C['accent'])
        self.bar.grid()

    def meta(self, event):
        if event.get('uploader'):
            self.title.configure(text='@' + event['uploader'])
        if event.get('title'):
            self.sub.configure(text=shorten(event['title'], 140))

    def progress(self, event):
        self.bar.set(event['percent'] / 100)
        self._badge(f"{event['percent']:.0f} %", C['accent'])

    def done(self, event):
        self.state = 'existing' if event.get('existing') else 'done'
        self.path = event['path']
        self.meta(event)
        self.bar.grid_remove()
        if self.state == 'existing':
            self._dot(C['muted'])
            self._badge('Déjà présente', C['muted'])
        else:
            self._dot(C['ok'])
            self._badge(f"Enregistrée ✓  {human_size(event.get('size'))}", C['ok'])
        self.action.grid(row=1, column=2, sticky='e', padx=(self.app.px(12), self.app.px(12)))

    def fail(self, message):
        self.state, self.error = 'failed', message
        self.bar.grid_remove()
        self._dot(C['bad'])
        self._badge('Échec', C['bad'])
        self.sub.configure(text=message, fg=C['bad'])
        self.copy_btn.grid(row=1, column=2, sticky='e', padx=(self.app.px(12), self.app.px(12)))
        failure_log().info(error_report(self.url, message, self.detail))

    def copy_error(self):
        self.app.copy_text(error_report(self.url, self.error, self.detail))
        self.app._status('Erreur copiée', 'Colle-la dans ton signalement sur GitHub.')

    def cancel(self):
        if self.state in ('waiting', 'active'):
            self.state = 'cancelled'
            self.bar.grid_remove()
            self._dot(C['faint'])
            self._badge('Annulée', C['faint'])

    def reveal(self):
        if not self.path:
            return
        try:
            if WIN:
                subprocess.Popen(['explorer', '/select,', os.path.normpath(self.path)])
            else:
                self.app.open_path(Path(self.path).parent)
        except OSError as exc:
            messagebox.showerror('Fichier introuvable', str(exc), parent=self.app)


# ---------------------------------------------------------------- app

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.scale = max(1.0, self.winfo_fpixels('1i') / 96)
        self.settings = load_settings()
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.proc = None
        self.busy = False
        self.rows = {}
        self.pending = []
        self.clip_seen = ''
        self.clip_links = []
        default = Path.home() / 'Videos' / 'TikDrop'
        self.folder = Path(self.settings.get('folder') or default)
        self._fonts()
        self._window()
        self._styles()
        self._build()
        self.refresh_links()
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Control-Return>', lambda e: self.start())
        self.bind('<Activate>', self.check_clipboard)
        self.bind('<Configure>', self._on_resize)
        self.after(100, self.poll)
        self.after(400, self.check_clipboard)

    # ---- setup
    def px(self, n):
        return int(round(n * self.scale))

    def _fonts(self):
        family = 'Segoe UI' if WIN else tkfont.nametofont('TkDefaultFont').actual('family')
        font = lambda size, weight='normal': tkfont.Font(self, family=family, size=size, weight=weight)
        self.f_title = font(19, 'bold')
        self.f_body, self.f_bold = font(10), font(10, 'bold')
        self.f_small, self.f_small_bold = font(9), font(9, 'bold')
        self.f_label = font(8, 'bold')
        self.f_btn, self.f_btn_bold = font(10), font(10, 'bold')
        self.f_text = font(11)

    def _window(self):
        self.title('TikDrop')
        self.configure(bg=C['bg'])
        self.icon = make_icon(self, 64)
        self.iconphoto(True, self.icon, make_icon(self, 32))
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(self.px(900), sw - 60), min(self.px(720), sh - 90)
        self.geometry(f'{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}')
        self.minsize(min(self.px(660), w), min(self.px(540), h))
        if WIN:
            self.after(10, self._win_chrome)

    def _hwnd(self):
        import ctypes
        return ctypes.windll.user32.GetParent(self.winfo_id())

    def _win_chrome(self):
        """Dark title bar matching the window (Windows 10 20H1+ / 11)."""
        try:
            import ctypes
            hwnd = self._hwnd()
            dwm = ctypes.windll.dwmapi
            on = ctypes.c_int(1)
            if dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), 4):
                dwm.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(on), 4)
            r, g, b = (int(C['bg'][i:i + 2], 16) for i in (1, 3, 5))
            color = ctypes.c_int(r | g << 8 | b << 16)
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), 4)  # Windows 11 only
            # repaint the frame now (NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED)
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x1 | 0x2 | 0x4 | 0x10 | 0x20)
        except Exception:
            pass

    def _styles(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Vertical.TScrollbar', background=C['raised'], troughcolor=C['surface'],
                        bordercolor=C['surface'], lightcolor=C['raised'], darkcolor=C['raised'],
                        arrowcolor=C['muted'], gripcount=0, relief='flat')
        style.map('Vertical.TScrollbar', background=[('active', C['hover'])])

    def _card(self, parent):
        return tk.Frame(parent, bg=C['surface'], highlightthickness=1,
                        highlightbackground=C['line'], highlightcolor=C['line'])

    def _label(self, parent, text):
        return tk.Label(parent, text=text.upper(), font=self.f_label, fg=C['accent'], bg=parent.cget('bg'))

    def _build(self):
        px = self.px
        body = tk.Frame(self, bg=C['bg'], padx=px(24), pady=px(18))
        body.pack(fill='both', expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(3, weight=1)

        # header
        head = tk.Frame(body, bg=C['bg'])
        head.grid(row=0, column=0, sticky='ew', pady=(0, px(16)))
        self.logo = make_icon(self, px(44))
        tk.Label(head, image=self.logo, bg=C['bg']).pack(side='left')
        titles = tk.Frame(head, bg=C['bg'])
        titles.pack(side='left', padx=(px(14), 0))
        tk.Label(titles, text='TikDrop', font=self.f_title, fg=C['text'], bg=C['bg']).pack(anchor='w')
        tk.Label(titles, text='Tes vidéos TikTok, sur ton ordinateur.', font=self.f_body,
                 fg=C['muted'], bg=C['bg']).pack(anchor='w')
        tk.Label(head, text='v' + VERSION, font=self.f_small, fg=C['faint'], bg=C['bg']).pack(side='right', anchor='n')

        # links card
        card = self._card(body)
        card.grid(row=1, column=0, sticky='ew')
        card.columnconfigure(0, weight=1)
        inner = tk.Frame(card, bg=C['surface'], padx=px(18), pady=px(14))
        inner.grid(row=0, column=0, sticky='ew')
        inner.columnconfigure(0, weight=1)
        top = tk.Frame(inner, bg=C['surface'])
        top.grid(row=0, column=0, sticky='ew')
        self._label(top, 'Liens TikTok').pack(side='left')
        tk.Label(top, text='Un lien par ligne, ou le texte de partage complet', font=self.f_small,
                 fg=C['faint'], bg=C['surface']).pack(side='right')
        self.text_box = tk.Frame(inner, bg=C['raised'], highlightthickness=1,
                                 highlightbackground=C['line'], highlightcolor=C['line'])
        self.text_box.grid(row=1, column=0, sticky='ew', pady=(px(10), px(10)))
        self.links = tk.Text(self.text_box, height=4, bg=C['raised'], fg=C['text'], font=self.f_text,
                             insertbackground=C['accent'], selectbackground=C['select'],
                             selectforeground=C['text'], relief='flat', bd=0, padx=px(12), pady=px(10),
                             wrap='word', undo=True, highlightthickness=0)
        self.links.pack(fill='both', expand=True)
        self.placeholder = tk.Label(self.text_box, font=self.f_text, fg=C['faint'], bg=C['raised'],
                                    text='Colle un lien, par ex. https://www.tiktok.com/@auteur/video/…', cursor='xterm')
        self.placeholder.place(x=px(13), y=px(10))
        self.placeholder.bind('<Button-1>', lambda e: self.links.focus_set())
        self.links.bind('<<Modified>>', self._on_modified)
        self.links.bind('<FocusIn>', lambda e: self._focus_box(True))
        self.links.bind('<FocusOut>', lambda e: self._focus_box(False))
        self.links.bind('<Control-Return>', lambda e: (self.start(), 'break')[1])
        tools = tk.Frame(inner, bg=C['surface'])
        tools.grid(row=2, column=0, sticky='ew')
        self.count_ok = tk.Label(tools, font=self.f_small, fg=C['muted'], bg=C['surface'])
        self.count_ok.pack(side='left')
        self.count_bad = tk.Label(tools, font=self.f_small, fg=C['warn'], bg=C['surface'])
        self.count_bad.pack(side='left')
        self.paste_btn = Button(tools, self, 'Coller', self.paste, small=True)
        self.paste_btn.pack(side='right')
        self.clear_btn = Button(tools, self, 'Vider', self.clear, kind='ghost', small=True)
        self.clear_btn.pack(side='right', padx=(0, px(6)))

        # clipboard banner
        self.banner = tk.Frame(card, bg=C['banner'], padx=px(18), pady=px(8))
        self.banner.columnconfigure(0, weight=1)
        self.banner_text = tk.Label(self.banner, font=self.f_small_bold, fg=C['accent'], bg=C['banner'], anchor='w')
        self.banner_text.grid(row=0, column=0, sticky='ew')
        Button(self.banner, self, 'Ignorer', self.clip_dismiss, kind='ghost', small=True).grid(row=0, column=1)
        Button(self.banner, self, 'Ajouter', self.clip_add, kind='primary', small=True).grid(row=0, column=2, padx=(px(6), 0))

        # folder card
        fcard = self._card(body)
        fcard.grid(row=2, column=0, sticky='ew', pady=(px(12), 0))
        frow = tk.Frame(fcard, bg=C['surface'], padx=px(18), pady=px(12))
        frow.pack(fill='x')
        self._label(frow, 'Dossier').pack(side='left', padx=(0, px(14)))
        Button(frow, self, 'Ouvrir', self.open_folder, kind='ghost', small=True).pack(side='right')
        self.browse_btn = Button(frow, self, 'Changer…', self.browse, small=True)
        self.browse_btn.pack(side='right', padx=(px(12), px(6)))
        self.folder_lbl = tk.Label(frow, font=self.f_body, fg=C['text'], bg=C['surface'], anchor='w', cursor='hand2')
        self.folder_lbl.pack(side='left', fill='x', expand=True)
        self.folder_lbl.bind('<Button-1>', lambda e: None if self.busy else self.browse())
        self._show_folder()

        # queue card
        qcard = self._card(body)
        qcard.grid(row=3, column=0, sticky='nsew', pady=(px(12), 0))
        qcard.columnconfigure(0, weight=1)
        qcard.rowconfigure(1, weight=1)
        qhead = tk.Frame(qcard, bg=C['surface'], padx=px(18), pady=px(12))
        qhead.grid(row=0, column=0, columnspan=2, sticky='ew')
        self._label(qhead, 'File d’attente').pack(side='left')
        self.queue_info = tk.Label(qhead, font=self.f_small, fg=C['muted'], bg=C['surface'])
        self.queue_info.pack(side='right')
        tk.Frame(qcard, bg=C['line'], height=1).grid(row=0, column=0, columnspan=2, sticky='sew')
        self.list = tk.Canvas(qcard, bg=C['surface'], highlightthickness=0, bd=0, yscrollincrement=px(24),
                              height=px(120))
        self.list.grid(row=1, column=0, sticky='nsew')
        self.scroll = ttk.Scrollbar(qcard, orient='vertical', command=self.list.yview)
        self.list.configure(yscrollcommand=self.scroll.set)
        self.list_inner = tk.Frame(self.list, bg=C['surface'])
        self.list_window = self.list.create_window(0, 0, anchor='nw', window=self.list_inner)
        self.list_inner.bind('<Configure>', lambda e: self._sync_scroll())
        self.list.bind('<Configure>', lambda e: (self.list.itemconfigure(self.list_window, width=e.width), self._sync_scroll()))
        self.list.bind('<Enter>', lambda e: self.bind_all('<MouseWheel>', self._wheel))
        self.list.bind('<Leave>', lambda e: self.unbind_all('<MouseWheel>'))
        self.empty = tk.Label(qcard, text='Les vidéos à télécharger apparaîtront ici.',
                              font=self.f_body, fg=C['faint'], bg=C['surface'])
        self.empty.place(in_=self.list, relx=0.5, rely=0.5, anchor='center')

        # footer
        foot = tk.Frame(body, bg=C['bg'])
        foot.grid(row=4, column=0, sticky='ew', pady=(px(14), 0))
        foot.columnconfigure(0, weight=1)
        self.total_bar = ProgressLine(foot, self, height=5, trough=C['raised'])
        self.total_bar.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, px(12)))
        status = tk.Frame(foot, bg=C['bg'])
        status.grid(row=1, column=0, sticky='w')
        self.status = tk.Label(status, text='Prêt · aucun compte nécessaire', font=self.f_bold,
                               fg=C['text'], bg=C['bg'], anchor='w')
        self.status.pack(anchor='w')
        self.detail = tk.Label(status, text='Ctrl+Entrée pour lancer', font=self.f_small,
                               fg=C['muted'], bg=C['bg'], anchor='w')
        self.detail.pack(anchor='w')
        actions = tk.Frame(foot, bg=C['bg'])
        actions.grid(row=1, column=1, sticky='e')
        self.retry_btn = Button(actions, self, 'Réessayer', self.retry)
        self.cancel_btn = Button(actions, self, 'Annuler', self.cancel, kind='danger')
        self.start_btn = Button(actions, self, 'Télécharger', self.start, kind='primary')
        self.start_btn.pack(side='right')

    # ---- small UI pieces
    def _focus_box(self, focused):
        color = C['accent'] if focused else C['line']
        self.text_box.configure(highlightbackground=color, highlightcolor=color)
        self._placeholder()

    def _placeholder(self):
        empty = not self.links.get('1.0', 'end').strip()
        if empty and self.focus_get() is not self.links:
            self.placeholder.place(x=self.px(13), y=self.px(10))
        else:
            self.placeholder.place_forget()

    def _on_resize(self, event):
        if event.widget is self:
            lines = 4 if event.height >= self.px(660) else 2
            if int(self.links.cget('height')) != lines:
                self.links.configure(height=lines)

    def _on_modified(self, event=None):
        self.links.edit_modified(False)
        self.refresh_links()

    def _show_folder(self):
        text = str(self.folder)
        self.folder_lbl.configure(text=text if len(text) <= 64 else text[:22] + '…' + text[-41:])

    def _sync_scroll(self):
        self.list.configure(scrollregion=self.list.bbox('all') or (0, 0, 0, 0))
        needed = self.list_inner.winfo_reqheight() > self.list.winfo_height() > 1
        if needed:
            self.scroll.grid(row=1, column=1, sticky='ns')
        else:
            self.scroll.grid_remove()
            self.list.yview_moveto(0)

    def _wheel(self, event):
        if self.list_inner.winfo_reqheight() > self.list.winfo_height():
            self.list.yview_scroll(int(-event.delta / 120) or (-1 if event.delta > 0 else 1), 'units')

    def _reveal(self, row):
        """Scroll the queue so the active row is visible."""
        self.update_idletasks()
        total = self.list_inner.winfo_reqheight()
        view = self.list.winfo_height()
        if total <= view:
            return
        top, bottom = (f * total for f in self.list.yview())
        y, h = row.winfo_y(), row.winfo_reqheight()
        if y < top or y + h > bottom:
            self.list.yview_moveto(max(0, y + h - view) / total)

    def _status(self, text, detail=None, color=None):
        self.status.configure(text=text, fg=color or C['text'])
        if detail is not None:
            self.detail.configure(text=detail)

    def refresh_links(self):
        links, rejected = scan_links(self.links.get('1.0', 'end'))
        self.pending = links
        ok = f"{plural(len(links), 'vidéo')} prête{'s' if len(links) > 1 else ''}" if links else ''
        if not links and not rejected:
            ok = 'Aucun lien pour l’instant'
        bad = f"{' · ' if ok else ''}{plural(len(rejected), 'lien')} ignoré{'s' if len(rejected) > 1 else ''} (pas une vidéo TikTok)" if rejected else ''
        self.count_ok.configure(text=ok)
        self.count_bad.configure(text=bad)
        self.start_btn.set_text(f'Télécharger · {len(links)}' if len(links) > 1 else 'Télécharger')
        self.start_btn.set_enabled(bool(links) and not self.busy)
        self._placeholder()

    # ---- actions
    def paste(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            self._status('Le presse-papiers ne contient pas de texte.', '', C['warn'])
            return
        self._insert(text)

    def _insert(self, text):
        prefix = '\n' if self.links.get('1.0', 'end').strip() else ''
        if prefix and self.links.get('end-2c') == '\n':
            prefix = ''
        self.links.insert('end', prefix + text.strip())
        self.links.see('end')
        self.refresh_links()

    def clear(self):
        self.links.delete('1.0', 'end')
        self.refresh_links()

    def check_clipboard(self, event=None):
        if self.busy or (event is not None and event.widget is not self):
            return
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            return
        if clip == self.clip_seen:
            return
        links, _ = scan_links(clip)
        known = set(self.pending)
        self.clip_links = [link for link in links if link not in known]
        self.clip_text = clip
        if self.clip_links:
            n = len(self.clip_links)
            self.banner_text.configure(text=f"{plural(n, 'lien')} TikTok dans le presse-papiers")
            self.banner.grid(row=1, column=0, sticky='ew')
        else:
            self.banner.grid_remove()

    def copy_text(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.clip_seen = self.clip_text = text  # our own copy is not a new link to offer

    def clip_add(self):
        self._insert('\n'.join(self.clip_links))
        self.clip_dismiss()

    def clip_dismiss(self):
        self.clip_seen = getattr(self, 'clip_text', '')
        self.banner.grid_remove()

    def browse(self):
        initial = self.folder if self.folder.is_dir() else Path.home()
        selected = filedialog.askdirectory(parent=self, initialdir=str(initial), title='Dossier des vidéos')
        if selected:
            self.folder = Path(selected)
            self.settings['folder'] = str(self.folder)
            save_settings(self.settings)
            self._show_folder()

    def open_path(self, folder):
        if WIN:
            os.startfile(str(folder))
        else:
            subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(folder)])

    def open_folder(self):
        try:
            folder = self.folder.expanduser().resolve()
            folder.mkdir(parents=True, exist_ok=True)
            self.open_path(folder)
        except OSError as exc:
            messagebox.showerror('Dossier inaccessible', str(exc), parent=self)

    def set_busy(self, busy):
        self.busy = busy
        self.links.configure(state='disabled' if busy else 'normal',
                             fg=C['muted'] if busy else C['text'])
        for button in (self.paste_btn, self.clear_btn, self.browse_btn):
            button.set_enabled(not busy)
        self.retry_btn.pack_forget()
        if busy:
            self.banner.grid_remove()
            self.start_btn.pack_forget()
            self.cancel_btn.set_enabled(True)
            self.cancel_btn.pack(side='right')
        else:
            self.cancel_btn.pack_forget()
            self.start_btn.pack(side='right')
        self.refresh_links()

    def start(self, urls=None):
        urls = urls or list(self.pending)
        if self.busy or not urls:
            return
        try:
            folder = self.folder.expanduser().resolve()
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror('Dossier inaccessible', str(exc), parent=self)
            return
        for row in self.rows.values():
            row.destroy()
        self.rows = {}
        for url in urls:
            row = Row(self.list_inner, self, url)
            row.pack(fill='x')
            self.rows[url] = row
        self.empty.place_forget()
        self.list.yview_moveto(0)
        self.total, self.current = len(urls), 0
        self.stop.clear()
        self.total_bar.set(0, C['accent'])
        self._status('Démarrage…', '')
        self._queue_info()
        self.set_busy(True)
        threading.Thread(target=self.run_batch, args=(urls, str(folder)), daemon=True).start()

    def retry(self):
        self.start([url for url, row in self.rows.items() if row.state in ('failed', 'cancelled')])

    def run_batch(self, urls, folder):
        try:
            for index, url in enumerate(urls, 1):
                if self.stop.is_set():
                    break
                self.events.put((url, {'type': 'begin', 'index': index}))
                cmd = ([sys.executable] if getattr(sys, 'frozen', False)
                       else [sys.executable, str(Path(__file__).resolve())]) + ['--worker', url, folder]
                try:
                    ok = run_worker(cmd, lambda event, url=url: self.events.put((url, event)), self._started)
                    if not ok and not self.stop.is_set():
                        self.events.put((url, {'type': 'failed'}))
                except OSError as exc:
                    self.events.put((url, {'type': 'error', 'message': 'Impossible de lancer le téléchargement.',
                                           'detail': repr(exc)}))
                    self.events.put((url, {'type': 'failed'}))
                finally:
                    self.proc = None
        finally:
            self.events.put(('', {'type': 'batch_done', 'cancelled': self.stop.is_set()}))

    def _started(self, proc):
        self.proc = proc
        if self.stop.is_set():
            proc.terminate()

    def cancel(self):
        if not self.busy:
            return
        self.stop.set()
        self.cancel_btn.set_enabled(False)
        self._status('Annulation en cours…', '')
        proc = self.proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def _counts(self):
        counts = {}
        for row in self.rows.values():
            counts[row.state] = counts.get(row.state, 0) + 1
        return counts

    def _queue_info(self):
        c = self._counts()
        finished = c.get('done', 0) + c.get('existing', 0) + c.get('failed', 0)
        self.queue_info.configure(text=f'{finished} / {len(self.rows)} terminée{"s" if finished > 1 else ""}')
        return finished

    def _overall(self, fraction=0.0):
        finished = self._queue_info()
        if self.rows:
            self.total_bar.set((finished + fraction) / len(self.rows))

    def poll(self):
        try:
            while True:
                url, event = self.events.get_nowait()
                self._handle(self.rows.get(url), event)
        except queue.Empty:
            pass
        self.after(80, self.poll)

    def _handle(self, row, event):
        kind = event.get('type')
        if kind == 'batch_done':
            return self._finish(event['cancelled'])
        if row is None:
            return
        if kind == 'begin':
            row.begin()
            self._reveal(row)
            self.current = event['index']
            self._status(f'Vidéo {self.current} sur {self.total}', 'Connexion à TikTok…')
            self._overall()
        elif kind == 'meta':
            row.meta(event)
        elif kind == 'progress':
            row.progress(event)
            parts = []
            if event.get('total'):
                parts.append(f"{human_size(event['downloaded'])} sur {human_size(event['total'])}")
            if event.get('speed'):
                parts.append(f"{human_size(event['speed'])}/s")
            if event.get('eta') is not None:
                parts.append('reste ' + human_eta(event['eta']))
            self.detail.configure(text=' · '.join(parts))
            self._overall(event['percent'] / 100)
        elif kind == 'done':
            row.done(event)
            self.detail.configure(text=shorten(event['path'], 110))
            self._overall()
        elif kind == 'error':
            row.error = event.get('message') or ''
            row.detail = event.get('detail') or ''
        elif kind == 'failed':
            row.fail(row.error or 'Le téléchargement n’a pas abouti.')
            self._overall()

    def _finish(self, cancelled):
        for row in self.rows.values():
            row.cancel()
        self.set_busy(False)
        c = self._counts()
        parts = []
        if c.get('done'):
            parts.append(f"{plural(c['done'], 'enregistrée')}")
        if c.get('existing'):
            parts.append(f"{c['existing']} déjà présente{'s' if c['existing'] > 1 else ''}")
        if c.get('failed'):
            parts.append(plural(c['failed'], 'échec'))
        if c.get('cancelled'):
            parts.append(f"{c['cancelled']} annulée{'s' if c['cancelled'] > 1 else ''}")
        color = C['bad'] if c.get('failed') and not (c.get('done') or c.get('existing')) else None
        self._status(('Annulé' if cancelled else 'Terminé') + ' · ' + (', '.join(parts) or 'rien à faire'),
                     None, color)
        self._overall()
        saved = [r for r in self.rows.values() if r.state in ('done', 'existing')]
        if saved:
            self.detail.configure(text='Clique sur « Afficher » pour retrouver une vidéo.')
        elif c.get('failed'):
            self.detail.configure(text='Vérifie que les vidéos sont publiques, puis réessaie.')
        else:
            self.detail.configure(text='')
        retry = c.get('failed', 0) + c.get('cancelled', 0)
        if retry:
            self.retry_btn.set_text(f'Réessayer · {retry}')
            self.retry_btn.pack(side='right', padx=(0, self.px(8)), after=self.start_btn)
        self._notify()

    def _notify(self):
        if self.focus_displayof() is not None:
            return
        self.bell()
        if WIN:
            try:
                import ctypes
                ctypes.windll.user32.FlashWindow(self._hwnd(), True)
            except Exception:
                pass

    def close(self):
        if self.busy and not messagebox.askyesno(
                'Téléchargement en cours', 'Quitter TikDrop et annuler le téléchargement en cours ?', parent=self):
            return
        self.cancel()
        self.destroy()


def enable_dpi_awareness():
    if WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        raise SystemExit(worker(sys.argv[2], sys.argv[3]))
    enable_dpi_awareness()
    App().mainloop()
