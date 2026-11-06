import json
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent.meta import build_meta_event, normalize_sql
from app.agent.nodes.run_sql import run_sql
from app.agent.state import DataAgentState
from app.api.dependencies import get_query_service
from app.api.routers.query_router import query_router
from app.services.query_service import QueryService


def make_state(**overrides) -> DataAgentState:
    """构造一个只带测试关心的字段的状态"""
    state = DataAgentState(query="统计华北地区的销售总额")
    state.update(overrides)
    return state


class NormalizeSqlTest(unittest.TestCase):
    def test_plain_sql_is_only_trimmed(self):
        self.assertEqual(normalize_sql("  SELECT 1  "), "SELECT 1")

    def test_sql_fence_block_is_removed(self):
        self.assertEqual(normalize_sql("```sql\nSELECT 1\n```"), "SELECT 1")

    def test_language_free_fence_block_is_removed(self):
        self.assertEqual(normalize_sql("```\nSELECT 1\n```"), "SELECT 1")

    def test_inline_fence_is_removed(self):
        self.assertEqual(normalize_sql("```sql SELECT 1```"), "SELECT 1")

    def test_multi_line_sql_keeps_inner_newlines(self):
        raw = "```sql\nSELECT a,\n       b\nFROM t\n```"
        self.assertEqual(normalize_sql(raw), "SELECT a,\n       b\nFROM t")

    def test_empty_input_returns_empty_string(self):
        self.assertEqual(normalize_sql(""), "")
        self.assertEqual(normalize_sql("   "), "")


class BuildMetaEventTest(unittest.TestCase):
    def test_event_carries_sql_keywords_and_metrics(self):
        state = make_state(
            sql="```sql\nSELECT SUM(amount) FROM dw.dwd_order\n```",
            keywords=["华北", "销售额"],
            metric_infos=[
                {
                    "name": "GMV",
                    "description": "成交总额",
                    "relevant_columns": ["dw.dwd_order.amount"],
                    "alias": ["成交额"],
                }
            ],
        )

        event = build_meta_event(state)

        self.assertEqual(event["type"], "meta")
        self.assertEqual(event["sql"], "SELECT SUM(amount) FROM dw.dwd_order")
        self.assertEqual(event["keywords"], ["华北", "销售额"])
        self.assertEqual(
            event["metrics"],
            [{"name": "GMV", "description": "成交总额", "alias": ["成交额"]}],
        )

    def test_raw_query_is_filtered_out_of_keywords(self):
        # 关键词抽取节点会把原始问题放进关键词列表做检索兜底，展示时不应出现
        state = make_state(
            query="统计华北地区的销售总额",
            keywords=["华北", "统计华北地区的销售总额", "销售额"],
        )

        self.assertEqual(build_meta_event(state)["keywords"], ["华北", "销售额"])

    def test_keywords_are_deduplicated_and_trimmed(self):
        state = make_state(keywords=[" 华北 ", "华北", "销售额", ""])

        self.assertEqual(build_meta_event(state)["keywords"], ["华北", "销售额"])

    def test_keywords_are_capped(self):
        state = make_state(keywords=[f"关键词{index}" for index in range(30)])

        self.assertEqual(len(build_meta_event(state)["keywords"]), 12)

    def test_missing_state_fields_fall_back_to_empty_values(self):
        event = build_meta_event(make_state())

        self.assertEqual(event["sql"], "")
        self.assertEqual(event["keywords"], [])
        self.assertEqual(event["metrics"], [])

    def test_metric_without_name_is_skipped(self):
        state = make_state(
            metric_infos=[
                {"name": "", "description": "空指标", "alias": []},
                {"name": "AOV", "description": "客单价", "alias": []},
            ]
        )

        self.assertEqual([item["name"] for item in build_meta_event(state)["metrics"]], ["AOV"])


class FakeDWRepository:
    """只记录被执行的 SQL，并返回预置结果"""

    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed_sql = None

    async def run(self, sql):
        self.executed_sql = sql
        return self.rows


class FakeRuntime:
    """模拟 LangGraph 运行时，收集节点写出的所有流式事件"""

    def __init__(self, repository):
        self.context = {"dw_mysql_repository": repository}
        self.events = []

    def stream_writer(self, event):
        self.events.append(event)


class RunSqlMetaEventTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_sql_emits_meta_between_progress_and_result(self):
        repository = FakeDWRepository([{"销售总额": 41099.5}])
        runtime = FakeRuntime(repository)
        state = make_state(
            sql="SELECT SUM(amount) FROM dw.dwd_order",
            keywords=["华北", "统计华北地区的销售总额"],
            metric_infos=[{"name": "GMV", "description": "成交总额", "alias": []}],
        )

        await run_sql(state, runtime)

        self.assertEqual(
            [event["type"] for event in runtime.events],
            ["progress", "progress", "meta", "result"],
        )
        self.assertEqual(repository.executed_sql, "SELECT SUM(amount) FROM dw.dwd_order")

        meta = runtime.events[2]
        self.assertEqual(meta["sql"], "SELECT SUM(amount) FROM dw.dwd_order")
        self.assertEqual(meta["keywords"], ["华北"])
        self.assertEqual(meta["metrics"][0]["name"], "GMV")

    async def test_meta_sql_is_normalized_for_display(self):
        runtime = FakeRuntime(FakeDWRepository([]))
        state = make_state(sql="```sql\nSELECT 1\n```")

        await run_sql(state, runtime)

        self.assertEqual(runtime.events[2]["sql"], "SELECT 1")


class MetaGraph:
    """产出 meta 事件的假图，用于验证 SSE 序列化"""

    async def astream(self, **kwargs):
        yield {"type": "meta", "sql": "SELECT 1", "keywords": ["华北"], "metrics": []}
        yield {"type": "result", "data": [{"销售总额": 1}]}


class QueryServiceMetaSseTest(unittest.IsolatedAsyncioTestCase):
    async def test_meta_event_is_serialized_as_sse(self):
        service = QueryService(
            meta_mysql_repository=None,
            embedding_client=None,
            dw_mysql_repository=None,
            column_qdrant_repository=None,
            metric_qdrant_repository=None,
            value_es_repository=None,
        )

        with patch("app.services.query_service.graph", MetaGraph()):
            chunks = [chunk async for chunk in service.query("统计华北地区的销售总额")]

        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(chunk.startswith("data: ") and chunk.endswith("\n\n") for chunk in chunks))

        meta_payload = json.loads(chunks[0][len("data: ") :].strip())
        self.assertEqual(meta_payload["type"], "meta")
        self.assertEqual(meta_payload["keywords"], ["华北"])
        # 中文不应被转义成 \uXXXX，便于排查线上问题
        self.assertIn("华北", chunks[0])


class MetaHttpContractTest(unittest.TestCase):
    """走真实路由和 QueryService，验证 meta 事件能穿透到 HTTP 响应体"""

    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(query_router)
        service = QueryService(
            meta_mysql_repository=None,
            embedding_client=None,
            dw_mysql_repository=None,
            column_qdrant_repository=None,
            metric_qdrant_repository=None,
            value_es_repository=None,
        )
        self.app.dependency_overrides[get_query_service] = lambda: service
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.app.dependency_overrides.clear()

    def test_streamed_response_contains_meta_before_result(self):
        with patch("app.services.query_service.graph", MetaGraph()):
            response = self.client.post(
                "/api/query", json={"query": "统计华北地区的销售总额"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.headers["content-type"].startswith("text/event-stream")
        )

        body = response.text
        self.assertIn('"type": "meta"', body)
        self.assertIn('"type": "result"', body)
        # meta 必须先于 result 到达，前端才能在拿到结果时同时渲染查询依据
        self.assertLess(body.index('"type": "meta"'), body.index('"type": "result"'))
        self.assertIn("华北", body)


if __name__ == "__main__":
    unittest.main()
