#!/usr/bin/python3
"""Resume only configured USB queues whose device is currently discoverable."""
import logging
import os
import subprocess
import time

os.environ['LC_ALL'] = 'C'
os.environ['CUPS_SERVER'] = '/run/cups/cups.sock'
logging.basicConfig(level=logging.INFO)


def output(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=20).stdout


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run as root')
    # รอ enumeration / backend พร้อม และลองซ้ำหลังเสียบหรือเปิดสวิตช์ USB
    for attempt in range(5):
        time.sleep(3)
        try:
            detected = {line.split(maxsplit=1)[1].strip() for line in output('lpinfo', '-v').splitlines() if ' ' in line}
            for line in output('lpstat', '-v').splitlines():
                if not line.startswith('device for ') or ': ' not in line:
                    continue
                queue, uri = line[len('device for '):].split(': ', 1)
                if uri.startswith(('usb://', 'hp:/usb/')) and uri in detected:
                    # เปิดรับงานต่อโดยไม่ลบงานที่ค้าง และไม่แตะคิวเครือข่าย
                    output('cupsenable', queue)
                    output('cupsaccept', queue)
                    logging.info('Enabled USB queue %s', queue)
        except (subprocess.SubprocessError, OSError):
            logging.exception('USB recovery pass %s failed', attempt + 1)
            if attempt == 4:
                raise


if __name__ == '__main__':
    main()
