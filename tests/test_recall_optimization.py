import unittest
from unittest.mock import patch

import yaml
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.agent.nodes.filter_table import (
    FILTER_COLUMN_FIELDS,
    apply_selection,
    build_filter_payload,
)
from app.agent.nodes.recall_column import recall_column
from app.agent.nodes.recall_metric import recall_metric
from app.agent.recall_utils import embed_in_batches
from app.agent.state import DataAgentState
from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo


class FakeEmbeddingClient:
    """记录每次批量请求的文本，并返回定长向量"""

    def __init__(self, dim: int = 2):
        self.dim = dim
        self.calls: list[list[str]] = []

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(text))] * self.dim for text in texts]


class FakeColumnRepository:
    def __init__(self):
        self.received: list[list[float]] = []

    async def search(self, embedding):
        self.received.append(embedding)
        return [
            ColumnInfo(
                id="fact_order.order_amount",
                name="order_amount",
                type="decimal",
                role="度量",
                examples=[62190.0],
                description="订单金额",
                alias=["销售额"],
                table_id="fact_order",
            )
        ]


class FakeMetricRepository:
    def __init__(self):
        self.received: list[list[float]] = []

    async def search(self, embedding):
        self.received.append(embedding)
        return [
            MetricInfo(
                id="GMV",
                name="GMV",
                description="成交总额",
                relevant_columns=["fact_order.order_amount"],
                alias=["成交额"],
            )
        ]


class FakeRuntime:
    def __init__(self, context):
        self.context = context
        self.events = []

    def stream_writer(self, event):
        self.events.append(event)


def extension_llm(words: list[str]):
    """构造一个直接把扩展词作为 AI 消息返回的假模型"""
    payload = AIMessage(content=str(words).replace("'", '"'))
    return RunnableLambda(lambda _: payload)


class EmbedInBatchesTest(unittest.IsolatedAsyncioTestCase):
    async def test_empty_input_does_not_call_client(self):
        client = FakeEmbeddingClient()

        self.assertEqual(await embed_in_batches(client, []), [])
        self.assertEqual(client.calls, [])

    async def test_vectors_keep_input_order(self):
        client = FakeEmbeddingClient()

        vectors = await embed_in_batches(client, ["a", "bbbb", "cc"])

        # 假客户端的向量首元素是文本长度，可以据此校验顺序
        self.assertEqual([vector[0] for vector in vectors], [1.0, 4.0, 2.0])

    async def test_long_input_is_split_into_batches(self):
        client = FakeEmbeddingClient()
        texts = [f"词{index}" for index in range(20)]

        vectors = await embed_in_batches(client, texts, batch_size=8)

        self.assertEqual([len(call) for call in client.calls], [8, 8, 4])
        self.assertEqual(len(vectors), 20)

    async def test_count_mismatch_raises(self):
        class ShortClient:
            async def aembed_documents(self, texts):
                return [[0.0, 0.0]]

        with self.assertRaises(ValueError):
            await embed_in_batches(ShortClient(), ["a", "b"])


class RecallColumnTest(unittest.IsolatedAsyncioTestCase):
    async def test_keywords_are_embedded_in_one_batch(self):
        client = FakeEmbeddingClient()
        repository = FakeColumnRepository()
        runtime = FakeRuntime(
            {
                "column_qdrant_repository": repository,
                "embedding_client": client,
            }
        )
        state = DataAgentState(query="统计华北地区的销售总额", keywords=["华北", "销售额"])

        with patch(
            "app.agent.nodes.recall_column.llm", extension_llm(["销售额", "成交金额"])
        ):
            result = await recall_column(state, runtime)

        # 2 个原始关键词 + 2 个扩展词，去重后 3 个，应该合并成 1 次批量请求
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(len(client.calls[0]), 3)
        self.assertEqual(len(repository.received), 3)

        retrieved = result["retrieved_column_infos"]
        self.assertEqual([column.id for column in retrieved], ["fact_order.order_amount"])
        self.assertEqual(
            [event["type"] for event in runtime.events],
            ["progress", "progress"],
        )


class RecallMetricTest(unittest.IsolatedAsyncioTestCase):
    async def test_keywords_are_embedded_in_one_batch(self):
        client = FakeEmbeddingClient()
        repository = FakeMetricRepository()
        runtime = FakeRuntime(
            {
                "metric_qdrant_repository": repository,
                "embedding_client": client,
            }
        )
        state = DataAgentState(query="统计华北地区的销售总额", keywords=["销售总额"])

        with patch("app.agent.nodes.recall_metric.llm", extension_llm(["GMV", "成交额"])):
            result = await recall_metric(state, runtime)

        self.assertEqual(len(client.calls), 1)
        self.assertEqual(len(client.calls[0]), 3)
        self.assertEqual(len(repository.received), 3)
        self.assertEqual([metric.id for metric in result["retrieved_metric_infos"]], ["GMV"])


def sample_table_infos():
    return [
        {
            "name": "fact_order",
            "role": "事实表",
            "description": "订单事实表",
            "columns": [
                {
                    "name": "order_amount",
                    "type": "decimal",
                    "role": "度量",
                    "examples": [62190.0, 1115.0],
                    "description": "订单金额",
                    "alias": ["销售额"],
                },
                {
                    "name": "region_id",
                    "type": "bigint",
                    "role": "外键",
                    "examples": [1, 2],
                    "description": "地区主键",
                    "alias": [],
                },
            ],
        },
        {
            "name": "dim_region",
            "role": "维度表",
            "description": "地区维表",
            "columns": [
                {
                    "name": "region_name",
                    "type": "varchar",
                    "role": "维度",
                    "examples": ["华北", "华东"],
                    "description": "地区名称",
                    "alias": ["大区"],
                }
            ],
        },
    ]


class FilterPayloadTest(unittest.TestCase):
    def test_payload_drops_examples_and_alias(self):
        payload = build_filter_payload(sample_table_infos())
        parsed = yaml.safe_load(payload)

        for table in parsed:
            self.assertEqual(set(table), {"name", "role", "description", "columns"})
            for column in table["columns"]:
                self.assertEqual(set(column), set(FILTER_COLUMN_FIELDS))
                self.assertNotIn("examples", column)
                self.assertNotIn("alias", column)

    def test_payload_keeps_role_for_join_and_semantics(self):
        parsed = yaml.safe_load(build_filter_payload(sample_table_infos()))

        # 提示词要求模型选出 join 所需的主外键，所以 role 必须保留
        self.assertEqual(parsed[0]["columns"][1]["role"], "外键")
        self.assertEqual(parsed[0]["columns"][0]["description"], "订单金额")

    def test_payload_is_smaller_than_full_dump(self):
        full = yaml.dump(
            sample_table_infos(), allow_unicode=True, sort_keys=False
        )
        trimmed = build_filter_payload(sample_table_infos())

        self.assertLess(len(trimmed), len(full))
        # 真实取值样例不应出现在提示词里
        self.assertNotIn("华北", trimmed)
        self.assertNotIn("62190", trimmed)


class ApplySelectionTest(unittest.TestCase):
    def test_only_selected_columns_survive(self):
        filtered = apply_selection(
            sample_table_infos(), {"fact_order": ["order_amount"]}
        )

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "fact_order")
        self.assertEqual(
            [column["name"] for column in filtered[0]["columns"]], ["order_amount"]
        )

    def test_table_not_in_selection_is_dropped(self):
        filtered = apply_selection(
            sample_table_infos(),
            {"fact_order": ["order_amount"], "dim_region": ["region_name"]},
        )

        self.assertEqual(
            [table["name"] for table in filtered], ["fact_order", "dim_region"]
        )

    def test_selected_table_with_empty_list_keeps_table_without_columns(self):
        # 保持与原有实现一致的行为：模型选中了表但没给字段时，表仍然保留
        filtered = apply_selection(sample_table_infos(), {"fact_order": []})

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["columns"], [])

    def test_original_table_infos_are_not_mutated(self):
        tables = sample_table_infos()

        apply_selection(tables, {"fact_order": ["order_amount"]})

        self.assertEqual(len(tables[0]["columns"]), 2)

    def test_non_dict_selection_raises(self):
        with self.assertRaises(ValueError):
            apply_selection(sample_table_infos(), ["fact_order"])


if __name__ == "__main__":
    unittest.main()
