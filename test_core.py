import tempfile
import unittest
from pathlib import Path
from core import download, friendly_error, parse_links, scan_links

URL = 'https://www.tiktok.com/@test/video/123456789'


class CoreTests(unittest.TestCase):
    def test_share_text_and_duplicates(self):
        self.assertEqual(parse_links(f'Regarde ! {URL}?share=1\n{URL}'), [URL])

    def test_short_links(self):
        self.assertEqual(parse_links('https://vm.tiktok.com/ABC12/'), ['https://vm.tiktok.com/ABC12'])

    def test_reject_unrelated_hosts_and_profiles(self):
        for url in ('https://tiktok.com.evil.com/@a/video/1', 'https://evil.com/x',
                    'https://www.tiktok.com/@profile', 'https://user@vm.tiktok.com/abc', ''):
            with self.subTest(url=url), self.assertRaises(ValueError):
                parse_links(url)

    def test_completed_file_and_progress(self):
        events = []
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test_123.mp4'
            class FakeDownloader:
                def __init__(self, options):
                    self.options = options
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def extract_info(self, url, download):
                    self.options['progress_hooks'][0]({'status': 'downloading', 'total_bytes': 100, 'downloaded_bytes': 50})
                    path.write_bytes(b'test fixture')
                    return {'title': 'Test'}
                def prepare_filename(self, info):
                    return str(path)
            download(URL, folder, events.append, FakeDownloader)
            self.assertEqual(events[0]['percent'], 50)
            self.assertEqual(events[-1]['type'], 'done')
            self.assertEqual(events[-1]['path'], str(path))
            self.assertFalse(events[-1]['existing'])

    def test_existing_file_and_metadata(self):
        events = []
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'auteur_123.mp4'
            path.write_bytes(b'already here')
            class Existing:
                def __init__(self, options):
                    self.options = options
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    pass
                def extract_info(self, url, download):
                    info = {'title': 'Titre', 'uploader': 'auteur'}
                    self.options['progress_hooks'][0]({'status': 'finished', 'info_dict': info})
                    return dict(info, requested_downloads=[{'filepath': str(path)}])
                def prepare_filename(self, info):
                    raise AssertionError('filepath from requested_downloads should win')
            download(URL, folder, events.append, Existing)
        self.assertEqual(events[0], {'type': 'meta', 'title': 'Titre', 'uploader': 'auteur'})
        self.assertTrue(events[-1]['existing'])
        self.assertEqual(events[-1]['uploader'], 'auteur')

    def test_scan_keeps_valid_links_and_reports_others(self):
        links, rejected = scan_links(f'Vu sur https://example.com/a et {URL}?lang=fr puis https://www.tiktok.com/@moi')
        self.assertEqual(links, [URL])
        self.assertEqual(rejected, ['https://example.com/a', 'https://www.tiktok.com/@moi'])

    def test_bad_port_is_rejected_not_crashing(self):
        self.assertEqual(scan_links('https://www.tiktok.com:99999/@a/video/1'), ([], ['https://www.tiktok.com:99999/@a/video/1']))

    def test_friendly_errors(self):
        self.assertIn('réseau', friendly_error('ERROR: [TikTok] 6748451240264420610: Your IP address is blocked from accessing this post'))
        self.assertIn('supprimée', friendly_error('ERROR: [TikTok] 1: Video not available, status code 10204'))
        self.assertEqual(friendly_error('ERROR: quelque chose de neuf'), 'quelque chose de neuf')

    def test_no_false_success_for_missing_file(self):
        class Missing:
            def __init__(self, options):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def extract_info(self, *args, **kwargs):
                return {'title': 'missing'}
            def prepare_filename(self, info):
                return 'does-not-exist-123456789.mp4'
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(RuntimeError):
            download(URL, folder, lambda e: None, Missing)


if __name__ == '__main__':
    unittest.main()
