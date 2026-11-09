"""French desktop interface for TikDrop (MIT)."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from core import parse_links, worker


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('TikDrop · Téléchargeur TikTok')
        self.geometry('860x820')
        self.minsize(800, 800)
        self.configure(bg='#10131c')
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.proc = None
        self.busy = False
        self.rows = {}
        self.folder = tk.StringVar(value=str(Path.home() / 'Videos' / 'TikDrop'))
        self.status = tk.StringVar(value='Prêt · Aucun compte nécessaire')
        self.detail = tk.StringVar(value='')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10), background='#10131c', foreground='#e9edf8')
        style.configure('TButton', background='#293147', foreground='#e9edf8', padding=10, borderwidth=0)
        style.map('TButton', background=[('active', '#3c4965')], foreground=[('disabled', '#7a8295')])
        style.configure('Accent.TButton', background='#24d6b5', foreground='#081b18', font=('Segoe UI', 10, 'bold'))
        style.map('Accent.TButton', background=[('active', '#56ead0'), ('disabled', '#263d3b')])
        style.configure('Treeview', background='#191f2d', fieldbackground='#191f2d', foreground='#e9edf8', rowheight=32, borderwidth=0)
        style.configure('Treeview.Heading', background='#263047', foreground='#e9edf8', padding=8)
        style.configure('Horizontal.TProgressbar', troughcolor='#293147', background='#24d6b5', borderwidth=0)
        style.configure('TEntry', fieldbackground='#191f2d', foreground='#e9edf8', insertcolor='#24d6b5')
        body = tk.Frame(self, bg='#10131c', padx=30, pady=24)
        body.pack(fill='both', expand=True)
        tk.Label(body, text='TikDrop', font=('Segoe UI', 29, 'bold'), fg='#ffffff', bg='#10131c').pack(anchor='w')
        tk.Label(body, text='Tes vidéos TikTok, sur ton ordinateur.', font=('Segoe UI', 12), fg='#9ba9c2', bg='#10131c').pack(anchor='w', pady=(2, 22))
        tk.Label(body, text='01  COLLE TES LIENS', font=('Segoe UI', 10, 'bold'), bg='#10131c', fg='#24d6b5').pack(anchor='w')
        self.links = tk.Text(body, height=4, bg='#191f2d', fg='#ffffff', insertbackground='#24d6b5', relief='flat', padx=12, pady=12, font=('Segoe UI', 11), wrap='word', undo=True)
        self.links.pack(fill='x', pady=(8, 8))
        row = tk.Frame(body, bg='#10131c')
        row.pack(fill='x')
        self.paste_btn = ttk.Button(row, text='Coller le presse-papiers', command=self.paste)
        self.paste_btn.pack(side='left')
        tk.Label(row, text='Un ou plusieurs liens · doublons ignorés', bg='#10131c', fg='#9ba9c2').pack(side='right')
        tk.Label(body, text='02  CHOISIS LE DOSSIER', font=('Segoe UI', 10, 'bold'), bg='#10131c', fg='#24d6b5').pack(anchor='w', pady=(20, 8))
        row = tk.Frame(body, bg='#10131c')
        row.pack(fill='x')
        self.folder_entry = ttk.Entry(row, textvariable=self.folder)
        self.folder_entry.pack(side='left', fill='x', expand=True, ipady=8)
        self.browse_btn = ttk.Button(row, text='Parcourir…', command=self.browse)
        self.browse_btn.pack(side='left', padx=(8, 0))
        ttk.Button(row, text='Ouvrir', command=self.open_folder).pack(side='left', padx=(8, 0))
        row = tk.Frame(body, bg='#10131c')
        row.pack(fill='x', pady=(20, 14))
        self.start_btn = ttk.Button(row, text='Télécharger les vidéos', style='Accent.TButton', command=self.start)
        self.start_btn.pack(side='left')
        self.cancel_btn = ttk.Button(row, text='Annuler', command=self.cancel, state='disabled')
        self.cancel_btn.pack(side='left', padx=8)
        self.table = ttk.Treeview(body, columns=('link', 'state'), show='headings', height=4, selectmode='browse')
        self.table.heading('link', text='VIDÉO')
        self.table.heading('state', text='ÉTAT')
        self.table.column('link', width=500)
        self.table.column('state', width=160, stretch=False)
        self.table.pack(fill='both', expand=True)
        self.bar = ttk.Progressbar(body, maximum=100)
        self.bar.pack(fill='x', pady=(14, 8))
        tk.Label(body, textvariable=self.status, bg='#10131c', fg='#e9edf8', anchor='w').pack(fill='x')
        tk.Label(body, textvariable=self.detail, bg='#10131c', fg='#9ba9c2', anchor='w', wraplength=770).pack(fill='x', pady=(4, 0))
        tk.Label(body, text='Open source · MIT · Télécharge tes créations ou les vidéos dont tu as l’autorisation.', bg='#10131c', fg='#77849e', font=('Segoe UI', 9)).pack(anchor='w', pady=(14, 0))
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(100, self.poll)

    def paste(self):
        try:
            text = self.clipboard_get()
            self.links.insert('end', ('\n' if self.links.get('1.0', 'end').strip() else '') + text)
        except tk.TclError:
            self.status.set('Le presse-papiers ne contient pas de texte.')

    def browse(self):
        selected = filedialog.askdirectory(initialdir=Path.home(), title='Dossier des vidéos')
        if selected:
            self.folder.set(selected)

    def open_folder(self):
        try:
            folder = Path(self.folder.get()).expanduser().resolve()
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == 'win32':
                os.startfile(str(folder))
            else:
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(folder)])
        except OSError as exc:
            messagebox.showerror('Dossier inaccessible', str(exc))

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.start_btn, self.paste_btn, self.browse_btn, self.folder_entry):
            widget.configure(state='disabled' if busy else 'normal')
        self.links.configure(state='disabled' if busy else 'normal')
        self.cancel_btn.configure(state='normal' if busy else 'disabled')

    def start(self):
        if self.busy:
            return
        try:
            urls = parse_links(self.links.get('1.0', 'end'))
            if not self.folder.get().strip():
                raise ValueError('Choisis un dossier de destination.')
            folder = Path(self.folder.get()).expanduser().resolve()
            folder.mkdir(parents=True, exist_ok=True)
        except (ValueError, OSError) as exc:
            messagebox.showerror('Vérifie les informations', str(exc))
            return
        self.table.delete(*self.table.get_children())
        self.rows = {url: self.table.insert('', 'end', values=(url, 'En attente')) for url in urls}
        self.stop.clear()
        self.detail.set('')
        self.bar['value'] = 0
        self.set_busy(True)
        threading.Thread(target=self.run_batch, args=(urls, str(folder)), daemon=True).start()

    def run_batch(self, urls, folder):
        successes = failures = 0
        try:
            for index, url in enumerate(urls, 1):
                if self.stop.is_set():
                    break
                self.events.put((url, {'type': 'begin', 'index': index, 'total': len(urls)}))
                cmd = ([sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, str(Path(__file__).resolve())]) + ['--worker', url, folder]
                done = False
                try:
                    self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    if self.stop.is_set():
                        self.proc.terminate()
                    for line in self.proc.stdout:
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        done |= event.get('type') == 'done'
                        self.events.put((url, event))
                    code = self.proc.wait()
                    if not self.stop.is_set():
                        if code == 0 and done:
                            successes += 1
                        else:
                            failures += 1
                            self.events.put((url, {'type': 'failed'}))
                except OSError as exc:
                    failures += 1
                    self.events.put((url, {'type': 'error', 'message': str(exc)}))
                    self.events.put((url, {'type': 'failed'}))
                finally:
                    self.proc = None
        finally:
            self.events.put(('', {'type': 'batch_done', 'successes': successes, 'failures': failures, 'cancelled': self.stop.is_set()}))

    def cancel(self):
        self.stop.set()
        self.cancel_btn.configure(state='disabled')
        self.status.set('Annulation en cours…')
        proc = self.proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def poll(self):
        try:
            while True:
                url, event = self.events.get_nowait()
                kind = event.get('type')
                if kind == 'begin':
                    self.table.set(self.rows[url], 'state', 'Connexion…')
                    self.bar['value'] = 0
                    self.status.set(f"Vidéo {event['index']} / {event['total']}")
                elif kind == 'progress':
                    self.bar['value'] = event['percent']
                    self.table.set(self.rows[url], 'state', f"{event['percent']:.0f} %")
                    self.detail.set(f"{event['speed'] / 1024 / 1024:.1f} Mo/s")
                elif kind == 'done':
                    self.bar['value'] = 100
                    self.table.set(self.rows[url], 'state', 'Enregistrée ✓')
                    self.detail.set(event['path'])
                elif kind in ('warning', 'error'):
                    self.detail.set(event.get('message', '')[:400])
                elif kind == 'failed':
                    self.table.set(self.rows[url], 'state', 'Échec')
                elif kind == 'batch_done':
                    for row in self.rows.values():
                        if self.table.set(row, 'state') not in ('Enregistrée ✓', 'Échec'):
                            self.table.set(row, 'state', 'Annulée')
                    self.set_busy(False)
                    prefix = 'Annulé' if event['cancelled'] else 'Terminé'
                    self.status.set(f"{prefix} · {event['successes']} enregistrée(s), {event['failures']} échec(s)")
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def close(self):
        self.cancel()
        self.destroy()


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        raise SystemExit(worker(sys.argv[2], sys.argv[3]))
    if sys.platform == 'win32' and getattr(sys, 'frozen', False):
        import ctypes
        console = ctypes.windll.kernel32.GetConsoleWindow()
        if console:
            ctypes.windll.user32.ShowWindow(console, 0)
    App().mainloop()
