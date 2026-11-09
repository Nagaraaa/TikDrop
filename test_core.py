import tempfile
import unittest
from pathlib import Path
from core import download, parse_links

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
