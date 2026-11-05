import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_query_service
from app.api.routers.query_router import query_router


class FakeQueryService:
    def __init__(self):
        self.received_query = None

    async def query(self, query):
        self.received_query = query
        yield 'data: {"type":"progress","step":"测试","status":"success"}\n\n'
        yield 'data: {"type":"result","data":[{"测试值":1}]}\n\n'


class ApiContractTest(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(query_router)
        self.fake_service = FakeQueryService()
        self.app.dependency_overrides[get_query_service] = lambda: self.fake_service
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.app.dependency_overrides.clear()

    def test_query_endpoint_returns_sse(self):
        response = self.client.post(
            "/api/query", json={"query": "测试问题"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.headers["content-type"].startswith("text/event-stream")
        )
        self.assertIn('"type":"progress"', response.text)
        self.assertIn('"type":"result"', response.text)
        self.assertEqual(self.fake_service.received_query, "测试问题")

    def test_missing_query_returns_422(self):
        response = self.client.post("/api/query", json={})
        self.assertEqual(response.status_code, 422)

    def test_non_string_query_returns_422(self):
        response = self.client.post("/api/query", json={"query": 123})
        self.assertEqual(response.status_code, 422)

    def test_openapi_contains_query_endpoint(self):
        schema = self.app.openapi()
        self.assertIn("/api/query", schema["paths"])
        self.assertIn("post", schema["paths"]["/api/query"])


if __name__ == "__main__":
    unittest.main()