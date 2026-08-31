import tempfile
import unittest
from pathlib import Path

from taskuary.server import _index_response


class WebEntrypointTests(unittest.TestCase):
    def test_index_is_never_cached(self):
        with tempfile.TemporaryDirectory() as d:
            index = Path(d) / 'index.html'
            index.write_text('<html>ready</html>', encoding='utf-8')
            response = _index_response(index)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store, must-revalidate')
        self.assertIn(b'ready', response.body)

    def test_missing_index_during_build_returns_a_self_healing_503(self):
        with tempfile.TemporaryDirectory() as d:
            response = _index_response(Path(d) / 'index.html')

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers['retry-after'], '1')
        self.assertEqual(response.headers['cache-control'], 'no-store, must-revalidate')
        self.assertIn(b'http-equiv="refresh"', response.body)
        self.assertIn(b'Taskuary is updating', response.body)


if __name__ == '__main__':
    unittest.main()
