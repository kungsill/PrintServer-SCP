# Validation — 2026-10-27

- Host: Windows, Python 3.13, Git Bash 5.3.9
- `bash -n setup-scpprint-armbian.sh`: PASS
- `bash -n install.sh`: PASS
- `bash -n scripts/healthcheck.sh`: PASS
- `bash install.sh --help`: PASS; performs no installation
- `python -m unittest discover -s tests -v`: 22 tests PASS
- `node --check agent/static/dashboard.js`: PASS
- Test dependencies: FastAPI 0.92.0, httpx 0.24.1
- Coverage: authentication; dedicated PDF/RAW routes; queue validation; upload limits; temporary file cleanup; exact CUPS config idempotence/policy preservation; TCP RAW EOF framing and size rejection; USB recovery excludes disconnected/network queues; Dashboard/static loading; status with no configured queues; explicit queue-clear confirmation; privileged helper rejects invalid/unknown queues and unauthorized peer UIDs.
- Chrome: visually checked Thai Dashboard against localhost preview data; token connection, scheduler/queue/job/USB metrics and enabled controls observed. Preview refuses real print/cancel actions. Screenshot: `dist/dashboard-preview.jpg` (mock state).
- Release: ZIP integrity, Python AST parsing, LF endings and SHA-256 manifest checked by `scripts/package_release.py`.

Not executed on this host: ARM64 apt installation, actual CUPS/Samba config parsers, systemd/udev activation, mDNS/Windows discovery, physical printing, zram/ramlog. The installer checks configs and services on the target. A real printer acceptance test is still required.
