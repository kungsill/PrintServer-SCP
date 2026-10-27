import json
from pathlib import Path
import struct
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agent'))
import test_agent
import api
import common
import queue_control


class DashboardAPI(unittest.TestCase):
    setUp = test_agent.PrintAPI.setUp
    assert_spool_empty = test_agent.PrintAPI.assert_spool_empty

    def test_dashboard_and_static_load_without_revealing_status(self):
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn('SCPPrint', page.text)
        self.assertNotIn(api.TOKEN, page.text)
        self.assertIn("frame-ancestors 'none'", page.headers['Content-Security-Policy'])
        self.assertEqual(self.client.get('/static/dashboard.js').status_code, 200)
        self.assertEqual(self.client.get('/status').status_code, 401)

    def test_dedicated_endpoints_dispatch_correct_format(self):
        for endpoint, content_type, data, raw in [('/print/pdf', 'application/pdf', b'%PDF-test', False),
                                                ('/print/raw', 'application/octet-stream', b'\x1b@raw', True)]:
            with self.subTest(endpoint=endpoint), patch.object(api, 'submit', return_value='queued') as submit:
                self.headers['Content-Type'] = content_type
                response = self.client.post(endpoint + '?printer=USB_Printer', content=data, headers=self.headers)
                self.assertEqual(response.status_code, 202)
                self.assertEqual(submit.call_args.args[2], raw)
                self.assert_spool_empty()

    def test_pdf_endpoint_does_not_accept_raw_content_type(self):
        self.headers['Content-Type'] = 'application/octet-stream'
        with patch.object(api, 'submit') as submit:
            response = self.client.post('/print/pdf?printer=USB_Printer', content=b'raw', headers=self.headers)
        self.assertEqual(response.status_code, 415)
        submit.assert_not_called()

    def test_clear_requires_token_and_explicit_boolean_confirmation(self):
        url = '/queue/clear?printer=USB_Printer'
        headers = {'Authorization': self.headers['Authorization']}
        with patch.object(api, 'clear_queue', return_value={'ok': True}) as clear:
            self.assertEqual(self.client.post(url, json={'confirm': True}).status_code, 401)
            self.assertEqual(self.client.post(url, json={'confirm': False}, headers=headers).status_code, 400)
            self.assertEqual(self.client.post(url, json={'confirm': 'true'}, headers=headers).status_code, 422)
            clear.assert_not_called()
            self.assertEqual(self.client.post(url, json={'confirm': True}, headers=headers).status_code, 200)
            clear.assert_called_once_with('USB_Printer')

    def test_snapshot_reports_no_queues_as_an_empty_list(self):
        def command(args, **kwargs):
            if args == ('lpstat', '-r'):
                return subprocess.CompletedProcess(args, 0, 'scheduler is running\n', '')
            if args == ('lsusb',):
                return subprocess.CompletedProcess(args, 0, 'Bus 001 Device 001: ID 1d6b:0002 Linux Foundation\n', '')
            return subprocess.CompletedProcess(args, 1, '', 'lpstat: No destinations added.\n')
        with patch.object(api.subprocess, 'run', side_effect=command):
            response = self.client.get('/status', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['printers'], [])
        self.assertIn('Bus 001', response.json()['lsusb']['output'])


class RootQueueControl(unittest.TestCase):
    def test_no_queue_or_flag_cannot_cancel_everything(self):
        for queue in ('', '-a', 'queue; reboot', None, 'queue/instance'):
            with self.subTest(queue=queue), patch.object(queue_control.subprocess, 'run') as run:
                with self.assertRaises(ValueError):
                    queue_control.execute(queue)
                run.assert_not_called()

    def test_cancel_targets_only_validated_queue(self):
        with patch.object(queue_control.subprocess, 'run') as run:
            self.assertTrue(queue_control.execute('USB_Printer')['ok'])
            calls = [call.args[0] for call in run.call_args_list]
            self.assertEqual(calls, [['lpstat', '-h', '/run/cups/cups.sock', '-p', 'USB_Printer'],
                                     ['cancel', '-h', '/run/cups/cups.sock', '-a', 'USB_Printer']])

    def test_unknown_queue_never_reaches_cancel(self):
        with patch.object(queue_control.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'lpstat')) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                queue_control.execute('Missing')
            self.assertEqual(run.call_count, 1)

    def test_peer_uid_is_checked_before_reading_commands(self):
        connection = Mock()
        connection.getsockopt.return_value = struct.pack('3i', 123, 999, 999)
        # Windows ไม่มี SO_PEERCRED; mock เฉพาะค่าคงที่เพื่อทดสอบเส้นทางตรวจ UID
        with patch.object(queue_control.socket, 'SO_PEERCRED', 17, create=True):
            with self.assertRaises(PermissionError):
                queue_control.handle(connection, 500)
        connection.recv.assert_not_called()

    def test_valid_peer_and_json_request(self):
        connection = Mock()
        connection.getsockopt.return_value = struct.pack('3i', 123, 500, 500)
        connection.recv.return_value = json.dumps({'printer': 'USB_Printer'}).encode() + b'\n'
        with patch.object(queue_control.socket, 'SO_PEERCRED', 17, create=True), \
             patch.object(queue_control, 'execute', return_value={'ok': True}) as execute:
            self.assertEqual(queue_control.handle(connection, 500), {'ok': True})
            execute.assert_called_once_with('USB_Printer')
