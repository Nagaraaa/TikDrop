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


# Fake worker: follows a plan per URL ("ok", "error", "nofile", "crash") and
# tags "done" with its process id, to check that one process serves the batch.
FAKE = r"""
import json, os, sys
plan = json.loads(sys.argv[1])
urls = sys.stdin.read().split()
def emit(url, **event):
    print(json.dumps(dict(event, url=url)), flush=True)
for url in urls:
    action = plan.get(url, 'ok')
    emit(url, type='begin')
    if action == 'crash':
        print('Traceback: boom', file=sys.stderr, flush=True)
        sys.exit(3)
    if action == 'ok':
        emit(url, type='done', path=str(os.getpid()))
    if action == 'error':
        emit(url, type='error', message='Vidéo introuvable', detail='ERROR: 404')
    emit(url, type='end', ok=action != 'error')
print('[1, 2]')  # stray output is ignored
"""
URLS = [f'https://www.tiktok.com/@t/video/{n}' for n in (1, 2, 3)]


class WorkerTests(unittest.TestCase):
    def run_worker(self, plan=None, cmd=None):
        events = {}
        cmd = cmd or [sys.executable, '-c', FAKE, json.dumps(plan or {})]
        left = app.run_worker(cmd, URLS, lambda url, event: events.setdefault(url, []).append(event))
        return left, events

    def kinds(self, events, url):
        return [event['type'] for event in events.get(url, [])]

    def test_whole_batch_in_one_process(self):
        left, events = self.run_worker()
        self.assertEqual(left, [])
        for url in URLS:
            self.assertEqual(self.kinds(events, url), ['begin', 'done'])
        self.assertEqual(len({events[url][1]['path'] for url in URLS}), 1)

    def test_reported_error_fails_only_that_video(self):
        left, events = self.run_worker({URLS[1]: 'error'})
        self.assertEqual(left, [])
        self.assertEqual(self.kinds(events, URLS[1]), ['begin', 'error', 'failed'])
        self.assertEqual(events[URLS[1]][1]['detail'], 'ERROR: 404')
        self.assertEqual(self.kinds(events, URLS[2]), ['begin', 'done'])

    def test_success_without_file_is_a_failure(self):
        left, events = self.run_worker({URLS[0]: 'nofile'})
        self.assertEqual(self.kinds(events, URLS[0]), ['begin', 'failed'])

    def test_crash_fails_current_video_and_returns_the_rest(self):
        left, events = self.run_worker({URLS[1]: 'crash'})
        self.assertEqual(left, [URLS[2]])
        self.assertEqual(self.kinds(events, URLS[0]), ['begin', 'done'])
        self.assertEqual(self.kinds(events, URLS[1]), ['begin', 'error', 'failed'])
        detail = events[URLS[1]][1]['detail']
        self.assertIn('Code de sortie : 3', detail)
        self.assertIn('Traceback: boom', detail)
        self.assertNotIn(URLS[2], events)

    def test_worker_that_cannot_start_fails_every_video(self):
        cmd = [sys.executable, '-c', 'import sys; sys.stderr.write("ImportError: yt_dlp\\n"); sys.exit(2)']
        left, events = self.run_worker(cmd=cmd)
        self.assertEqual(left, [])
        for url in URLS:
            self.assertEqual(self.kinds(events, url), ['error', 'failed'])
            self.assertIn('ImportError: yt_dlp', events[url][0]['detail'])


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


class UpdateTests(unittest.TestCase):
    PAGE = 'https://github.com/Nagaraaa/TikDrop/releases/tag/v'

    def check(self, tag, current='1.2.0', url=None):
        release = {'tag_name': tag, 'html_url': url or self.PAGE + tag.lstrip('v')}
        with mock.patch.object(app, 'VERSION', current):
            return app.newer_release(lambda: release)

    def test_versions_compare_as_numbers(self):
        self.assertEqual(app.parse_version('v1.10.0'), (1, 10, 0))
        self.assertGreater(app.parse_version('1.10.0'), app.parse_version('1.9.9'))
        self.assertIsNone(app.parse_version('v2.0.0-beta'))

    def test_newer_release_is_offered(self):
        self.assertEqual(self.check('v1.10.0', current='1.9.0'), ('1.10.0', self.PAGE + '1.10.0'))

    def test_same_older_or_odd_releases_are_ignored(self):
        for tag in ('v1.2.0', 'v1.1.9', 'v9.0.0-rc1', 'nightly'):
            with self.subTest(tag=tag):
                self.assertIsNone(self.check(tag))
        self.assertIsNone(self.check('v9.0.0', url='https://example.com/piege'))

    def test_failures_are_silent(self):
        def offline():
            raise OSError('no network')
        self.assertIsNone(app.newer_release(offline))
        self.assertIsNone(app.newer_release(lambda: {'message': 'API rate limit exceeded'}))


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


    def test_update_turns_the_version_into_a_link(self):
        self.app._offer_update(None)
        self.assertEqual(self.app.version_lbl.cget('text'), 'v' + app.VERSION)
        with mock.patch.object(app.webbrowser, 'open') as browser:
            self.app._offer_update(('9.0.0', 'https://github.com/Nagaraaa/TikDrop/releases/tag/v9.0.0'))
            self.assertEqual(self.app.version_lbl.cget('text'), 'Nouvelle version 9.0.0 →')
            self.app.deiconify()  # mouse events only reach a visible window
            self.app.update()
            self.app.version_lbl.event_generate('<Button-1>', x=2, y=2)
            self.app.update()
            browser.assert_called_once_with('https://github.com/Nagaraaa/TikDrop/releases/tag/v9.0.0')


if __name__ == '__main__':
    unittest.main()
