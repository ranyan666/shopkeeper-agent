import unittest
from unittest.mock import patch

from app.agent.graph import graph
from app.services.query_service import QueryService


class FakeGraph:
    def __init__(self):
        self.received = None

    async def astream(self, **kwargs):
        self.received = kwargs
        yield {"type": "progress", "step": "测试", "status": "success"}
        yield {"type": "result", "data": [{"测试值": 1}]}


class FailingGraph:
    async def astream(self, **kwargs):
        raise RuntimeError("模拟图执行失败")
        yield {}


def create_service():
    return QueryService(
        meta_mysql_repository=None,
        embedding_client=None,
        dw_mysql_repository=None,
        column_qdrant_repository=None,
        metric_qdrant_repository=None,
        value_es_repository=None,
    )


class QueryServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_success_is_wrapped_as_sse(self):
        fake_graph = FakeGraph()
        with patch("app.services.query_service.graph", fake_graph):
            chunks = [
                chunk async for chunk in create_service().query("测试问题")
            ]

        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(chunk.endswith("\n\n") for chunk in chunks))
        self.assertIn('"type": "progress"', chunks[0])
        self.assertIn('"type": "result"', chunks[1])
        self.assertEqual(fake_graph.received["stream_mode"], "custom")
        self.assertEqual(
            fake_graph.received["input"]["query"], "测试问题"
        )

    async def test_graph_error_is_wrapped_as_sse(self):
        with patch("app.services.query_service.graph", FailingGraph()):
            chunks = [
                chunk async for chunk in create_service().query("测试问题")
            ]

        self.assertEqual(len(chunks), 1)
        self.assertIn('"type": "error"', chunks[0])
        self.assertIn("模拟图执行失败", chunks[0])
        self.assertTrue(chunks[0].endswith("\n\n"))

    def test_graph_contains_required_nodes(self):
        node_names = set(graph.get_graph().nodes.keys())
        required_nodes = {
            "extract_keywords",
            "recall_column",
            "recall_metric",
            "recall_value",
            "merge_retrieved_info",
            "filter_table",
            "filter_metric",
            "add_extra_context",
            "generate_sql",
            "validate_sql",
            "correct_sql",
            "run_sql",
        }
        self.assertTrue(required_nodes.issubset(node_names))


if __name__ == "__main__":
    unittest.main()