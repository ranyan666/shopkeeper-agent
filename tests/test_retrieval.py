import unittest

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class RetrievalIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        embedding_client_manager.init()
        qdrant_client_manager.init()
        es_client_manager.init()

    async def asyncTearDown(self):
        if embedding_client_manager.client is not None:
            await embedding_client_manager.client.async_client.close()
        await qdrant_client_manager.close()
        await es_client_manager.close()
        
    async def test_embedding_returns_1024_dimensions(self):
        embedding = await embedding_client_manager.client.aembed_query("销售总额")
        self.assertEqual(len(embedding), 1024)

    async def test_column_semantic_search(self):
        embedding = await embedding_client_manager.client.aembed_query("销售总额")
        repository = ColumnQdrantRepository(qdrant_client_manager.client)
        results = await repository.search(
            embedding, score_threshold=0.4, limit=10
        )
        result_ids = {item.id for item in results}
        self.assertIn("fact_order.order_amount", result_ids)

    async def test_metric_semantic_search(self):
        embedding = await embedding_client_manager.client.aembed_query("销售总额")
        repository = MetricQdrantRepository(qdrant_client_manager.client)
        results = await repository.search(
            embedding, score_threshold=0.4, limit=10
        )
        result_names = {item.name for item in results}
        self.assertIn("GMV", result_names)

    async def test_region_value_full_text_search(self):
        repository = ValueESRepository(es_client_manager.client)
        results = await repository.search("华北", score_threshold=0.1)
        values = {
            (item.column_id, item.value) for item in results
        }
        self.assertIn(("dim_region.region_name", "华北"), values)


if __name__ == "__main__":
    unittest.main()
