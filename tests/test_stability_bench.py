import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'stability_bench', Path(__file__).parents[1] / 'tools' / 'stability_bench.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class BenchmarkTests(unittest.TestCase):
    def test_failures_stay_in_success_denominator(self):
        result = bench.summarize([
            {'ok': True, 'total_s': 1.0},
            {'ok': False, 'total_s': 5.0},
            {'ok': True, 'total_s': 3.0},
        ])
        self.assertEqual(result['success_rate'], 0.6667)
        self.assertEqual(result['latency_success_only_s']['p50'], 2.0)
        self.assertEqual(result['failure_total_s'], [5.0])

    def test_empty_and_failed_runs_have_no_success_latency(self):
        self.assertIsNone(bench.summarize([])['success_rate'])
        result = bench.summarize([{'ok': False, 'total_s': 5.0}])
        self.assertIsNone(result['latency_success_only_s']['p95'])
        self.assertEqual(result['failed'], 1)

    def test_private_url_and_credential_redaction(self):
        url = 'https://203.0.113.8:8443/private-token/mihomo.yaml'
        error = bench.redact(url + ' credential=example-uuid peer=203.0.113.9',
                             [url, 'example-uuid'])
        self.assertNotIn('private-token', error)
        self.assertNotIn('example-uuid', error)
        self.assertNotIn('203.0.113.9', error)


if __name__ == '__main__':
    unittest.main()
