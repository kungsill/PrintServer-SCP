"""Development preview only: mock printer state, never send/cancel real jobs."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent'))
os.environ['SCPPRINT_TOKEN'] = 'preview-only-scpprint-not-for-production'
import api


def preview_snapshot():
    return {
        'scheduler': {'output': 'scheduler is running', 'exit_code': 0},
        'lpstat': {'output': 'printer USB_Printer is idle. enabled since Tue 27 Oct 2026\nsystem default destination: USB_Printer', 'exit_code': 0},
        'jobs': {'output': '', 'exit_code': 0},
        'lsusb': {'output': 'Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub\nBus 001 Device 002: ID 0000:0000 Preview USB Printer', 'exit_code': 0},
        'printers': [{'name': 'USB_Printer', 'state': 'idle', 'description': 'Preview printer', 'usb': True}],
        'max_upload_bytes': 33554432,
    }


def refuse(*args, **kwargs):
    raise OSError('Development preview cannot print or cancel jobs')


if __name__ == '__main__':
    import uvicorn
    api.snapshot = preview_snapshot
    api.submit = refuse
    api.clear_queue = refuse
    print('Preview token: preview-only-scpprint-not-for-production')
    uvicorn.run(api.app, host='127.0.0.1', port=18631)
