import os
import re
import subprocess
import json
import socket

os.environ['LC_ALL'] = 'C'
os.environ['CUPS_SERVER'] = 'localhost'
MAX_BYTES = int(os.environ.get('SCPPRINT_MAX_BYTES', '33554432'))
if not 1 <= MAX_BYTES <= 134217728:
    raise RuntimeError('SCPPRINT_MAX_BYTES must be 1..134217728')
SPOOL = '/var/spool/scpprint'
QUEUE_RE = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,126}\Z')


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=30).stdout.strip()


def printers():
    result = subprocess.run(['lpstat', '-p'], capture_output=True, text=True, timeout=30)
    # CUPS คืน exit code 1 เมื่อยังไม่มีคิว ไม่ถือว่า scheduler เสีย
    if result.returncode and 'No destinations added' not in result.stderr + result.stdout:
        result.check_returncode()
    return [line.split()[1] for line in result.stdout.splitlines() if line.startswith('printer ')]


def validate_queue(queue):
    if not QUEUE_RE.fullmatch(queue):
        raise ValueError('Invalid queue name')
    if queue not in printers():
        raise ValueError('Unknown CUPS queue')


def submit(path, queue, raw=False, copies=1, duplex=False):
    validate_queue(queue)
    args = ['lp', '-d', queue, '-t', 'SCPPrint', '-n', str(copies)]
    if raw:
        args += ['-o', 'raw']
    elif duplex:
        args += ['-o', 'sides=two-sided-long-edge']
    return run(*args, str(path))


def clear_queue(queue):
    """เรียก helper ผ่าน Unix socket; เว็บไม่มีสิทธิ์ root หรือ sudo"""
    validate_queue(queue)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(45)
        connection.connect('/run/scpprint-queue-control.sock')
        connection.sendall(json.dumps({'printer': queue}).encode() + b'\n')
        response = bytearray()
        while b'\n' not in response:
            chunk = connection.recv(1024)
            if not chunk:
                raise OSError('Queue control closed without response')
            response.extend(chunk)
            if len(response) > 4096:
                raise OSError('Invalid queue control response')
    result = json.loads(response)
    if not result.get('ok'):
        raise OSError('Queue control failed; inspect journal')
    return result
