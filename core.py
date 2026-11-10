"""TikDrop download engine. No shell commands or browser cookies."""
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

_URL = re.compile(r'https?://[^\s<>"«»]+')
_ANSI = re.compile(r'\x1b\[[0-9;]*m')


def _clean_link(raw):
    """Return the canonical video URL for ``raw``, or None if it is not one."""
    raw = raw.rstrip('.,;!?)。')
    try:
        parts = urlsplit(raw)
        port = parts.port
    except ValueError:
        return None
    host = (parts.hostname or '').lower()
    if parts.username or parts.password or port not in (None, 443, 80):
        return None
    short = host in ('vm.tiktok.com', 'vt.tiktok.com') and re.fullmatch(r'/[A-Za-z0-9]+/?', parts.path)
    normal = host in ('tiktok.com', 'www.tiktok.com', 'm.tiktok.com') and (
        re.fullmatch(r'/@[^/]+/video/\d+/?', parts.path)
        or re.fullmatch(r'/t/[A-Za-z0-9]+/?', parts.path))
    if not (short or normal):
        return None
    return urlunsplit(('https', host, parts.path.rstrip('/'), '', ''))


def scan_links(text):
    """Split pasted text into (valid video links, rejected URLs), deduplicated."""
    links, rejected = [], []
    for raw in _URL.findall(text):
        clean = _clean_link(raw)
        bucket, value = (links, clean) if clean else (rejected, raw)
        if value not in bucket:
            bucket.append(value)
    return links, rejected


def parse_links(text):
    """Strict variant: every URL must be a TikTok video link."""
    links, rejected = scan_links(text)
    if rejected:
        raise ValueError('Utilise un lien de vidéo TikTok (pas un profil) : ' + rejected[0])
    if not links:
        raise ValueError('Colle au moins un lien de vidéo TikTok.')
    return links


# First match wins: specific needles must come before broad ones
# ('requested format is not available' before 'not available', network errors
# before 'unable to download webpage', which wraps them).
_FRIENDLY = (
    (('ip address is blocked',), 'TikTok bloque cette vidéo depuis ton réseau. Réessaie plus tard ou avec une autre connexion.'),
    (('requested format is not available', 'no video formats'), 'Aucun format vidéo disponible (diaporama photo ?).'),
    (('log in', 'login', 'private', 'comfortable for some audiences'), 'Cette vidéo n’est pas publique ou demande une connexion.'),
    (('http error 404', 'not available', 'unavailable', 'removed', 'does not exist'), 'Vidéo introuvable : elle a peut-être été supprimée.'),
    (('http error 403',), 'TikTok refuse l’accès à cette vidéo (erreur 403).'),
    (('timed out', 'getaddrinfo', 'network is unreachable', 'connection', 'name resolution',
      # curl_cffi (used by the Windows build): resolve proxy/host, connect, timeout, receive
      'curl: (5)', 'curl: (6)', 'curl: (7)', 'curl: (28)', 'curl: (56)'), 'Problème de connexion Internet.'),
    (('unable to extract', 'unsupported url', 'unable to download webpage'), 'Impossible de lire la page TikTok. Une mise à jour de TikDrop peut être nécessaire.'),
    (('errno 28', 'no space left'), 'Plus assez d’espace disque.'),
    (('errno 13', 'permission denied'), 'Impossible d’écrire dans ce dossier.'),
)


def friendly_error(message):
    """Turn a raw yt-dlp/OS error into a short French explanation."""
    text = _ANSI.sub('', str(message)).strip()
    text = re.sub(r'^(ERROR:\s*)?(\[[^\]]+\]\s*)?([\w-]+:\s+)?', '', text)
    low = text.lower()
    for needles, friendly in _FRIENDLY:
        if any(n in low for n in needles):
            return friendly
    return text[:300] or 'Erreur inconnue.'


def download(url, destination, emit, factory=None):
    if parse_links(url) != [url]:
        raise ValueError('Lien TikTok non valide.')
    if factory is None:
        from yt_dlp import YoutubeDL
        factory = YoutubeDL
    target = Path(destination).resolve()
    target.mkdir(parents=True, exist_ok=True)
    state = {'meta': False, 'downloaded': False}

    class Logger:
        def debug(self, msg):
            pass

        def warning(self, msg):
            emit({'type': 'warning', 'message': msg})

        def error(self, msg):
            pass

    def progress(data):
        info = data.get('info_dict') or {}
        if not state['meta'] and info:
            state['meta'] = True
            emit({'type': 'meta', 'title': info.get('title') or '', 'uploader': info.get('uploader') or ''})
        if data.get('status') == 'downloading':
            state['downloaded'] = True
            total = data.get('total_bytes') or data.get('total_bytes_estimate') or 0
            done = data.get('downloaded_bytes') or 0
            emit({'type': 'progress', 'percent': min(99, 100 * done / total) if total else 0,
                  'speed': data.get('speed') or 0, 'eta': data.get('eta'),
                  'downloaded': done, 'total': total})

    options = {
        'format': 'best[ext=mp4]/best',  # combined audio/video; no FFmpeg dependency
        # Prefer H.264: TikTok also serves H.265, which Windows only plays with a paid extension.
        'format_sort': ['vcodec:h264'],
        'outtmpl': str(target / '%(uploader)s_%(id)s.%(ext)s'),
        'windowsfilenames': True, 'noplaylist': True, 'overwrites': False,
        'continuedl': True, 'socket_timeout': 20, 'retries': 2,
        'extractor_retries': 2, 'quiet': True, 'noprogress': True, 'no_warnings': False,
        'logger': Logger(), 'progress_hooks': [progress],
    }
    with factory(options) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info or info.get('_type') in ('playlist', 'multi_video'):
            raise RuntimeError('Ce lien ne correspond pas à une vidéo unique.')
        requested = info.get('requested_downloads') or [{}]
        filename = requested[0].get('filepath') or ydl.prepare_filename(info)
        path = Path(filename)
        if not path.is_file():
            raise RuntimeError('Le moteur n’a pas produit de fichier vidéo.')
        emit({'type': 'done', 'path': str(path), 'title': info.get('title') or '',
              'uploader': info.get('uploader') or '', 'size': path.stat().st_size,
              'existing': not state['downloaded']})


def _std_stream(name, mode):
    """sys.stdin/stdout, even in a windowed (no console) frozen build where they are None."""
    stream = getattr(sys, name)
    if stream is not None:
        return stream
    if sys.platform == 'win32':
        import ctypes
        import msvcrt
        handle = ctypes.windll.kernel32.GetStdHandle({'stdin': -10, 'stdout': -11}[name])
        if handle not in (0, -1, None):
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY if mode == 'r' else os.O_WRONLY)
            return open(fd, mode, encoding='utf-8', buffering=1)
    return open(os.devnull, mode)


def worker(destination):
    """Download every URL read from stdin, one after the other, in this process.

    Each event is a JSON line tagged with its URL; every video starts with
    "begin" and finishes with "end" (ok true/false).
    """
    urls = _std_stream('stdin', 'r').read().split()  # read all first: the parent never blocks writing
    out = _std_stream('stdout', 'w')
    sys.stdout = out
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')
    failures = 0
    for url in urls:
        def emit(event, url=url):
            print(json.dumps(dict(event, url=url), ensure_ascii=True), file=out, flush=True)
        emit({'type': 'begin'})
        try:
            download(url, destination, emit)
            ok = True
        except Exception as exc:
            emit({'type': 'error', 'message': friendly_error(exc), 'detail': str(exc)[:600]})
            ok = False
        failures += not ok
        emit({'type': 'end', 'ok': ok})
    return 1 if failures else 0
