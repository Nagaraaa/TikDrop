import importlib.util
import io
import json
from contextlib import redirect_stdout
from unittest import mock
import tempfile
import unittest
from pathlib import Path
import core
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

    def test_specific_errors_win_over_broad_ones(self):
        self.assertIn('diaporama', friendly_error('ERROR: [TikTok] 1: Requested format is not available. '
                                                  'Use --list-formats for a list of available formats'))
        self.assertIn('connexion Internet', friendly_error('ERROR: [TikTok] 1: Unable to download webpage: '
                                                           '<urlopen error [Errno 11001] getaddrinfo failed>'))
        self.assertIn('mise à jour', friendly_error('ERROR: [TikTok] 1: Unable to extract universal data'))

    def test_curl_network_errors(self):
        for reason in ('curl: (6) Could not resolve host: www.tiktok.com',
                       'curl: (7) Failed to connect to www.tiktok.com port 443 after 0 ms: Could not connect to server',
                       'curl: (7) CONNECT tunnel failed, response 403'):
            with self.subTest(reason=reason):
                self.assertIn('connexion Internet', friendly_error(
                    f'ERROR: [TikTok] 1: Unable to download webpage: Failed to perform, {reason}. '
                    'See https://curl.se/libcurl/c/libcurl-errors.html first for more details.'))

    @unittest.skipUnless(importlib.util.find_spec('yt_dlp'), 'yt-dlp non installé')
    def test_prefers_h264_without_watermark(self):
        from yt_dlp import YoutubeDL
        captured = {}

        class Capture:
            def __init__(self, options):
                captured.update(options)
                raise RuntimeError('stop')
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(RuntimeError):
            download(URL, folder, lambda e: None, Capture)
        options = {k: captured[k] for k in ('format', 'format_sort')}

        def pick(formats):
            with YoutubeDL(dict(options, quiet=True, simulate=True)) as ydl:
                info = {'id': '1', 'title': 't', 'extractor': 'TikTok', 'extractor_key': 'TikTok',
                        'webpage_url': URL, 'formats': formats}
                return ydl.process_video_result(info, download=False)['format_id']

        def fmt(fid, vcodec, height, preference=-1):
            return {'format_id': fid, 'url': 'https://example.com/' + fid, 'ext': 'mp4', 'vcodec': vcodec,
                    'acodec': 'aac', 'height': height, 'width': height * 9 // 16, 'preference': preference}
        watermarked = fmt('download', 'h264', 1024, preference=-2)
        hevc = fmt('bytevc1_1080p', 'h265', 1920)
        self.assertEqual(pick([watermarked, fmt('h264_540p', 'h264', 1024), hevc]), 'h264_540p')
        self.assertEqual(pick([watermarked, hevc]), 'bytevc1_1080p')

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


    def test_worker_downloads_every_url_from_stdin(self):
        other = 'https://vm.tiktok.com/ABC12'
        def fake_download(url, destination, emit):
            if url == other:
                raise RuntimeError('ERROR: [TikTok] 1: Video not available')
            emit({'type': 'done', 'path': 'x.mp4'})
        out = io.StringIO()
        with mock.patch.object(core, 'download', fake_download), \
                mock.patch('sys.stdin', io.StringIO(f'{URL}\n{other}\n')), redirect_stdout(out):
            code = core.worker('dossier')
        events = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(code, 1)
        self.assertEqual([(e['url'] == URL, e['type']) for e in events],
                         [(True, 'begin'), (True, 'done'), (True, 'end'),
                          (False, 'begin'), (False, 'error'), (False, 'end')])
        self.assertTrue(events[2]['ok'])
        self.assertFalse(events[5]['ok'])
        self.assertIn('supprimée', events[4]['message'])


if __name__ == '__main__':
    unittest.main()
