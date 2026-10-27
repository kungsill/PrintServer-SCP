"""Run with python -m unittest discover -s tests -v (FastAPI + httpx required)."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agent'))
os.environ['SCPPRINT_TOKEN'] = 'test-token-' + 'x' * 32
import api
import common
from fastapi.testclient import TestClient

spec = importlib.util.spec_from_file_location('configure_cups', ROOT / 'scripts/configure_cups.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class PrintAPI(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        spool_patch = patch.object(api, 'SPOOL', self.directory.name)
        spool_patch.start()
        self.addCleanup(spool_patch.stop)
        printers_patch = patch.object(common, 'printers', return_value=['USB_Printer'])
        printers_patch.start()
        self.addCleanup(printers_patch.stop)
        self.client = TestClient(api.app)
        self.addCleanup(self.client.close)
        self.headers = {'Authorization': 'Bearer ' + os.environ['SCPPRINT_TOKEN'], 'Content-Type': 'application/pdf'}

    def send(self, content=b'%PDF-1.4\nexample', **kwargs):
        return self.client.post('/print?printer=USB_Printer', content=content, headers=self.headers, **kwargs)

    def assert_spool_empty(self):
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_unauthenticated_cannot_submit(self):
        with patch.object(api, 'submit') as submit:
            response = self.client.post('/print?printer=USB_Printer', content=b'%PDF-', headers={'Content-Type': 'application/pdf'})
        self.assertEqual(response.status_code, 401)
        submit.assert_not_called()
        self.assert_spool_empty()

    def test_pdf_copies_and_duplex_reach_cups_and_spool_is_removed(self):
        observed = []
        def submit(path, queue, raw, copies, duplex):
            observed.append((path.read_bytes(), queue, raw, copies, duplex))
            return 'request id is USB_Printer-42 (1 file(s))'
        with patch.object(api, 'submit', side_effect=submit):
            response = self.client.post('/print?printer=USB_Printer&copies=2&duplex=true',
                                        content=b'%PDF-1.4\ntest', headers=self.headers)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(observed, [(b'%PDF-1.4\ntest', 'USB_Printer', False, 2, True)])
        self.assert_spool_empty()

    def test_oversize_rejected_without_printing(self):
        with patch.object(api, 'MAX_BYTES', 8), patch.object(api, 'submit') as submit:
            response = self.send(b'%PDF-' + b'x' * 10)
        self.assertEqual(response.status_code, 413)
        submit.assert_not_called()
        self.assert_spool_empty()

    def test_invalid_pdf_and_empty_file_rejected(self):
        for content in (b'', b'not a PDF'):
            with self.subTest(content=content), patch.object(api, 'submit') as submit:
                self.assertEqual(self.send(content).status_code, 400)
                submit.assert_not_called()
                self.assert_spool_empty()

    def test_unknown_queue_rejected(self):
        with patch.object(api, 'submit') as submit:
            response = self.client.post('/print?printer=Unknown', content=b'%PDF-', headers=self.headers)
        self.assertEqual(response.status_code, 400)
        submit.assert_not_called()
        self.assert_spool_empty()

    def test_raw_dispatch(self):
        self.headers['Content-Type'] = 'application/octet-stream'
        with patch.object(api, 'submit', return_value='request id is USB_Printer-43') as submit:
            self.assertEqual(self.send(b'\x1b@RAW').status_code, 202)
            self.assertTrue(submit.call_args.args[2])
        self.assert_spool_empty()

    def test_cups_failure_cleans_spool(self):
        with patch.object(api, 'submit', side_effect=OSError('no CUPS')):
            self.assertEqual(self.send().status_code, 503)
        self.assert_spool_empty()

    def test_options_cannot_inject_flags(self):
        with patch.object(common, 'run', return_value='queued') as run:
            common.submit('/tmp/fixed-file', 'USB_Printer', copies=2, duplex=True)
            self.assertEqual(run.call_args.args, ('lp', '-d', 'USB_Printer', '-t', 'SCPPrint', '-n', '2',
                                                  '-o', 'sides=two-sided-long-edge', '/tmp/fixed-file'))
            with self.assertRaises(ValueError):
                common.submit('/tmp/fixed-file', '-h attacker')


class CUPSConfig(unittest.TestCase):
    def test_preserves_policy_and_replaces_existing_locations(self):
        original = '''LogLevel warn
Listen localhost:631
Listen /run/cups/cups.sock
<Location />
Order deny,allow
</Location>
<Location /admin>
Require user @SYSTEM
</Location>
<Policy default>
  <Limit All>
    Order deny,allow
  </Limit>
</Policy>
'''
        result = config.configure(original)
        self.assertIn('<Policy default>', result)
        self.assertIn('LogLevel warn', result)
        self.assertEqual(result.count('<Location />'), 1)
        self.assertEqual(result.count('Listen *:631'), 1)
        self.assertIn('DefaultEncryption Required', result)
        self.assertIn('Encryption Required', result)
        self.assertIn('Require user @SYSTEM', result)
        rerun = config.configure(result)
        self.assertEqual(rerun, result)
        self.assertEqual(rerun.count('Listen *:631'), 1)
        self.assertEqual(rerun.count('<Location /admin>'), 1)
        self.assertEqual(rerun.count('# Managed by SCPPrint'), 1)


if __name__ == '__main__':
    unittest.main()
