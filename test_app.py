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


if __name__ == '__main__':
    unittest.main()
