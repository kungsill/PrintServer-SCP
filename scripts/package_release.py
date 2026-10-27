#!/usr/bin/env python3
"""จัด ZIP สำหรับส่งไปกล่อง โดยไม่รวม .exe, virtualenv, cache และ token"""
import ast
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = [ROOT / name for name in ('setup-scpprint-armbian.sh', 'install.sh', 'README.md',
                                     'FLASH_GUIDE.md', 'VALIDATION.md', '.gitattributes', '.gitignore')]
    for directory in ('agent', 'config', 'scripts', 'systemd', 'tests'):
        files.extend(path for path in (ROOT / directory).rglob('*')
                     if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc')
    for path in files:
        if path.suffix == '.py':
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        if b'\r\n' in path.read_bytes():
            raise SystemExit(f'Use LF line endings: {path.relative_to(ROOT)}')
    output = ROOT / 'dist' / 'armbian-scpprint-server.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            entry = zipfile.ZipInfo('armbian-scpprint-server/' + path.relative_to(ROOT).as_posix())
            entry.create_system = 3
            entry.external_attr = (0o100755 if path.suffix == '.sh' else 0o100644) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, path.read_bytes())
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise SystemExit('ZIP verification failed')
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n', encoding='utf-8')
    print(f'{output}: {len(files)} files; ZIP/Python syntax/LF checks passed')
    print(f'SHA256: {digest}')


if __name__ == '__main__':
    main()
