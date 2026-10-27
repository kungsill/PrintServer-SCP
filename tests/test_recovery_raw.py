import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent'))
os.environ['SCPPRINT_QUEUE'] = 'USB_Printer'
import raw

spec = importlib.util.spec_from_file_location('usb_heal', ROOT / 'scripts/usb_heal.py')
usb_heal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usb_heal)


class USBRecovery(unittest.TestCase):
    def test_only_attached_usb_queues_are_resumed(self):
        commands = []
        def output(*args):
            commands.append(args)
            if args == ('lpinfo', '-v'):
                return 'direct usb://vendor/present\nnetwork ipp://remote/printer\n'
            if args == ('lpstat', '-v'):
                return ('device for Attached: usb://vendor/present\n'
                        'device for Missing: usb://vendor/absent\n'
                        'device for Network: ipp://remote/printer\n')
            return ''
        with patch.object(usb_heal.os, 'geteuid', return_value=0, create=True), \
             patch.object(usb_heal.time, 'sleep'), patch.object(usb_heal, 'output', side_effect=output):
            usb_heal.main()
        healed = [args for args in commands if args[0] in ('cupsenable', 'cupsaccept')]
        self.assertEqual(healed, [('cupsenable', 'Attached'), ('cupsaccept', 'Attached')] * 5)


class RAWReceiver(unittest.IsolatedAsyncioTestCase):
    async def exchange(self, content):
        server = await asyncio.start_server(raw.receive, '127.0.0.1', 0)
        try:
            port = server.sockets[0].getsockname()[1]
            reader, writer = await asyncio.open_connection('127.0.0.1', port)
            writer.write(content)
            await writer.drain()
            writer.write_eof()
            await asyncio.wait_for(reader.read(), timeout=3)
            writer.close()
            await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

    async def test_tcp_eof_submits_exact_bytes_and_cleans_up(self):
        observed = []
        def submit(path, queue, is_raw):
            observed.append((path.read_bytes(), queue, is_raw))
            return 'queued'
        with tempfile.TemporaryDirectory() as directory, patch.object(raw, 'SPOOL', directory), \
             patch.object(raw, 'submit', side_effect=submit):
            await self.exchange(b'\x1b@printer-ready')
            self.assertEqual(observed, [(b'\x1b@printer-ready', 'USB_Printer', True)])
            self.assertEqual(list(Path(directory).iterdir()), [])

    async def test_oversize_raw_is_not_submitted(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(raw, 'SPOOL', directory), \
             patch.object(raw, 'MAX_BYTES', 4), patch.object(raw, 'submit') as submit, \
             self.assertLogs(level='ERROR'):
            await self.exchange(b'too many bytes')
            submit.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])
