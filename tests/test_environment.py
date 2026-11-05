import json
import unittest
from urllib.request import urlopen

from app.conf.app_config import app_config


class EnvironmentSmokeTest(unittest.TestCase):
    def test_embedding_dimension(self):
        self.assertEqual(app_config.qdrant.embedding_size, 1024)

    def test_qdrant_is_available(self):
        with urlopen("http://127.0.0.1:6333/collections", timeout=5) as response:
            self.assertEqual(response.status, 200)
            data = json.load(response)
            self.assertEqual(data["status"], "ok")

    def test_elasticsearch_is_available(self):
        with urlopen("http://127.0.0.1:9200", timeout=5) as response:
            self.assertEqual(response.status, 200)
            data = json.load(response)
            self.assertIn("version", data)

    def test_embedding_service_is_available(self):
        with urlopen("http://127.0.0.1:8081/health", timeout=5) as response:
            self.assertEqual(response.status, 200)


if __name__ == "__main__":
    unittest.main()