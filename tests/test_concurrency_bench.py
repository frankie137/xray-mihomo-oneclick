from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ConcurrencyInputTests(unittest.TestCase):
    def reject(self, flags, message):
        script = Path(__file__).parents[1] / 'tools' / 'concurrency_bench.py'
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(script), '--private-config', '/nonexistent',
                 '--output', directory] + flags, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn(message, result.stderr)
        self.assertNotIn('FileNotFoundError', result.stderr)

    def test_concurrency_ceiling_and_order(self):
        for levels in (['0'], ['257'], ['32', '16'], ['16', '16']):
            self.reject(['--levels'] + levels, 'levels must increase')

    def test_no_private_config_sent_to_remote_proxy_or_controller(self):
        self.reject(['--proxy', 'http://untrusted.example:8080'], 'proxy on loopback')
        self.reject(['--controller', 'http://untrusted.example:9090'], 'controller must')

    def test_bounded_hold_and_repetitions(self):
        self.reject(['--hold-seconds', '31'], 'waves must')
        self.reject(['--waves', '6'], 'waves must')


if __name__ == '__main__':
    unittest.main()
