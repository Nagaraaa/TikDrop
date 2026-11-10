import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import app
except ImportError as exc:  # Python without Tkinter
    raise unittest.SkipTest(f'interface non testable : {exc}')

URL = 'https://www.tiktok.com/@test/video/123456789'


def python(code):
    return [sys.executable, '-c', code]


class WorkerTests(unittest.TestCase):
    def run_worker(self, code):
        events = []
        return app.run_worker(python(code), events.append), events

    def test_success_forwards_events(self):
        ok, events = self.run_worker('print(%r)' % json.dumps({'type': 'done', 'path': 'x.mp4'}))
        self.assertTrue(ok)
        self.assertEqual(events, [{'type': 'done', 'path': 'x.mp4'}])

    def test_reported_error_is_kept_as_is(self):
        error = {'type': 'error', 'message': 'Vidéo introuvable', 'detail': 'ERROR: 404'}
        ok, events = self.run_worker('import sys; print(%r); sys.exit(1)' % json.dumps(error))
        self.assertFalse(ok)
        self.assertEqual(events, [error])

    def test_crash_keeps_exit_code_and_output(self):
        ok, events = self.run_worker('import sys; print("[1, 2]"); sys.stderr.write("Traceback: boom\\n"); sys.exit(3)')
        self.assertFalse(ok)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['type'], 'error')
        self.assertIn('Code de sortie : 3', events[0]['detail'])
        self.assertIn('Traceback: boom', events[0]['detail'])
        self.assertIn('[1, 2]', events[0]['detail'])

    def test_exit_zero_without_file_is_a_failure(self):
        ok, events = self.run_worker('pass')
        self.assertFalse(ok)
        self.assertIn('Code de sortie : 0', events[0]['detail'])


class ReportTests(unittest.TestCase):
    def test_report_contents(self):
        report = app.error_report(URL, 'Problème de connexion Internet.', 'ERROR: getaddrinfo failed')
        self.assertTrue(report.startswith(f'TikDrop {app.VERSION} · yt-dlp '))
        self.assertIn(f'Lien : {URL}', report)
        self.assertIn('Erreur : Problème de connexion Internet.', report)
        self.assertIn('Détail : ERROR: getaddrinfo failed', report)

    def test_detail_identical_to_message_is_not_repeated(self):
        self.assertNotIn('Détail', app.error_report(URL, 'Erreur X', 'Erreur X'))

    def test_failures_are_written_to_the_log(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, {'APPDATA': folder}):
            app.failure_log.cache_clear()
            logger = app.failure_log()
            try:
                logger.info(app.error_report(URL, 'Erreur X', 'détail Y'))
                text = (Path(folder) / 'TikDrop' / 'tikdrop.log').read_text(encoding='utf-8')
            finally:
                for handler in list(logger.handlers):
                    handler.close()
                    logger.removeHandler(handler)
                app.failure_log.cache_clear()
        self.assertIn('Lien : ' + URL, text)
        self.assertIn('Détail : détail Y', text)


class InterfaceTests(unittest.TestCase):
    """Behaviour of the real window (skipped without a display)."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        patcher = mock.patch.dict(os.environ, {'APPDATA': folder.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        try:
            self.app = app.App()
        except app.tk.TclError as exc:
            self.skipTest(f'pas d’écran : {exc}')
        self.addCleanup(self.app.destroy)
        self.app.withdraw()

    def text(self):
        return self.app.links.get('1.0', 'end').strip()

    def test_banner_hides_once_the_link_is_in_the_box(self):
        self.app.clipboard_clear()
        self.app.clipboard_append(f'Regarde {URL}')
        self.app.check_clipboard()
        self.assertEqual(self.app.clip_links, [URL])
        self.app._insert(URL)  # pasted by hand instead of clicking "Ajouter"
        self.assertEqual(self.app.clip_links, [])
        self.assertFalse(self.app.banner.winfo_manager())

    def test_saved_links_leave_the_box(self):
        other = 'https://vm.tiktok.com/ABC12'
        self.app._insert(f'{URL}\nhttps://example.com/x\n{other}')
        saved, failed = (app.Row(self.app.list_inner, self.app, u) for u in (URL, other))
        saved.state, failed.state = 'existing', 'failed'
        self.app.rows = {URL: saved, other: failed}
        self.app._drop_saved_links()
        self.assertEqual(self.text(), other)
        self.assertEqual(self.app.pending, [other])

    def test_unknown_size_shows_a_label_not_zero_percent(self):
        row = app.Row(self.app.list_inner, self.app, URL)
        row.progress({'percent': 0, 'total': 0})
        self.assertEqual(row.badge.cget('text'), 'Téléchargement…')
        row.progress({'percent': 42.4, 'total': 100})
        self.assertEqual(row.badge.cget('text'), '42 %')


if __name__ == '__main__':
    unittest.main()
