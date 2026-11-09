"""TikDrop download engine. No shell commands or browser cookies."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def parse_links(text):
    """Accept copied share text; reject non-video and lookalike URLs."""
    links = []
    for raw in re.findall(r'https?://[^\s<>"\u00ab\u00bb]+', text):
        raw = raw.rstrip('.,;!?)\u3002')
        parts = urlsplit(raw)
        host = (parts.hostname or '').lower()
        if parts.username or parts.password or parts.port not in (None, 443, 80):
            raise ValueError('Lien non autorisé : ' + raw)
        short = host in ('vm.tiktok.com', 'vt.tiktok.com') and re.fullmatch(r'/[A-Za-z0-9]+/?', parts.path)
        normal = host in ('tiktok.com', 'www.tiktok.com', 'm.tiktok.com') and (
            re.fullmatch(r'/@[^/]+/video/\d+/?', parts.path)
            or re.fullmatch(r'/t/[A-Za-z0-9]+/?', parts.path))
        if not (short or normal):
            raise ValueError('Utilise un lien de vidéo TikTok (pas un profil) : ' + raw)
        clean = urlunsplit(('https', host, parts.path.rstrip('/'), '', ''))
        if clean not in links:
            links.append(clean)
    if not links:
        raise ValueError('Colle au moins un lien de vidéo TikTok.')
    return links


def download(url, destination, emit, factory=None):
    if parse_links(url) != [url]:
        raise ValueError('Lien TikTok non valide.')
    if factory is None:
        from yt_dlp import YoutubeDL
        factory = YoutubeDL
    target = Path(destination).resolve()
    target.mkdir(parents=True, exist_ok=True)

    class Logger:
        def debug(self, msg):
            pass
        def warning(self, msg):
            emit({'type': 'warning', 'message': msg})
        def error(self, msg):
            pass

    def progress(data):
        if data.get('status') == 'downloading':
            total = data.get('total_bytes') or data.get('total_bytes_estimate') or 0
            emit({'type': 'progress', 'percent': min(99, 100 * data.get('downloaded_bytes', 0) / total) if total else 0,
                  'speed': data.get('speed') or 0})

    options = {
        'format': 'best[ext=mp4]/best',  # combined audio/video; no FFmpeg dependency
        'outtmpl': str(target / '%(uploader)s_%(id)s.%(ext)s'),
        'windowsfilenames': True, 'noplaylist': True, 'overwrites': False,
        'continuedl': True, 'socket_timeout': 20, 'retries': 2,
        'extractor_retries': 2, 'quiet': True, 'no_warnings': False,
        'logger': Logger(), 'progress_hooks': [progress],
    }
    with factory(options) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info or info.get('_type') in ('playlist', 'multi_video'):
            raise RuntimeError('Ce lien ne correspond pas à une vidéo unique.')
        filename = ydl.prepare_filename(info)
        if not Path(filename).is_file():
            raise RuntimeError('Le moteur n’a pas produit de fichier vidéo.')
        emit({'type': 'done', 'path': filename, 'title': info.get('title', '')})


def worker(url, destination):
    import sys
    def emit(event):
        print(json.dumps(event, ensure_ascii=True), flush=True)
    try:
        download(url, destination, emit)
        return 0
    except Exception as exc:
        emit({'type': 'error', 'message': str(exc)})
        return 1
