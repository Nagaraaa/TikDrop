"""Complete dist/TikDrop after PyInstaller and zip it as dist/TikDrop-Windows.zip.

Run with the Python used for the build (Construire.cmd does it), so that the
bundled Python licence matches the interpreter inside the executable.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'
APP = DIST / 'TikDrop'
FILES = {  # source in the repository -> name next to TikDrop.exe
    ROOT / 'distribution' / 'README.md': 'README.md',
    ROOT / 'LICENSE': 'LICENSE',
    ROOT / 'THIRD_PARTY.md': 'THIRD_PARTY.md',
    ROOT / 'VERIFICATION.md': 'VERIFICATION.md',
    Path(sys.base_prefix) / 'LICENSE.txt': 'licenses/Python-LICENSE.txt',
}


def main():
    if not (APP / 'TikDrop.exe').is_file():
        sys.exit('dist/TikDrop/TikDrop.exe introuvable : lance PyInstaller d’abord.')
    for source, name in FILES.items():
        target = APP / name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(source, target)
    print(shutil.make_archive(str(DIST / 'TikDrop-Windows'), 'zip', root_dir=DIST, base_dir='TikDrop'))


if __name__ == '__main__':
    main()
