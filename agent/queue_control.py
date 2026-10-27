#!/usr/bin/python3
"""helper สิทธิ์ root แบบ socket activation: ยกเลิกได้เฉพาะคิวที่ระบุเท่านั้น"""
import json
import logging
import os
import re
import socket
import struct
import subprocess

QUEUE_RE = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,126}\Z')
CUPS_SOCKET = '/run/cups/cups.sock'
logging.basicConfig(level=logging.INFO)


def execute(queue):
    if not isinstance(queue, str) or not QUEUE_RE.fullmatch(queue):
        raise ValueError('Invalid queue name')
    env = dict(os.environ, LC_ALL='C', CUPS_SERVER=CUPS_SOCKET)
    # ยืนยันคิวจริงก่อน cancel; ไม่รับ flag หรือคำสั่งอื่นจาก request
    subprocess.run(['lpstat', '-h', CUPS_SOCKET, '-p', queue], env=env,
                   check=True, capture_output=True, timeout=10)
    subprocess.run(['cancel', '-h', CUPS_SOCKET, '-a', queue], env=env,
                   check=True, capture_output=True, timeout=20)
    logging.info('Cancelled all jobs on queue %s', queue)
    return {'ok': True, 'printer': queue, 'status': 'cancelled'}


def handle(connection, allowed_uid):
    # ตรวจผู้เรียกด้วย UID จาก kernel ป้องกันผู้ใช้อื่นแอบเรียก helper
    _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid not in (0, allowed_uid):
        raise PermissionError('Unauthorized local peer')
    connection.settimeout(5)
    data = bytearray()
    while b'\n' not in data:
        chunk = connection.recv(256)
        if not chunk:
            raise ValueError('Incomplete request')
        data.extend(chunk)
        if len(data) > 512:
            raise ValueError('Request too long')
    request = json.loads(data)
    if not isinstance(request, dict) or set(request) != {'printer'}:
        raise ValueError('Invalid request')
    return execute(request['printer'])


def main():
    import pwd  # Linux-only; แยก import เพื่อให้ unit test ฝั่งพัฒนาบน Windows ได้
    if os.geteuid() != 0:
        raise SystemExit('Root helper required')
    # StandardInput=socket ของ systemd ส่ง connected socket มาเป็น fd 0
    with socket.socket(fileno=os.dup(0)) as connection:
        try:
            result = handle(connection, pwd.getpwnam('scpprint').pw_uid)
        except Exception:
            logging.exception('Queue control request failed')
            result = {'ok': False}
        connection.sendall(json.dumps(result).encode() + b'\n')


if __name__ == '__main__':
    main()
