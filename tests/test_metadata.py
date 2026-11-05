import asyncio
import json
import unittest
from urllib.request import urlopen

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.conf.app_config import app_config


def get_json(url):
    with urlopen(url, timeout=10) as response:
        return json.load(response)


async def get_meta_counts():
    config = app_config.db_meta
    url = (
        f"mysql+asyncmy://{config.user}:{config.password}"
        f"@{config.host}:{config.port}/{config.database}"
    )
    engine = create_async_engine(url)
    sql = text(
        """
        SELECT 'table_info' AS item, COUNT(*) AS total FROM meta.table_info
        UNION ALL
        SELECT 'column_info', COUNT(*) FROM meta.column_info
        UNION ALL
        SELECT 'metric_info', COUNT(*) FROM meta.metric_info
        UNION ALL
        SELECT 'column_metric', COUNT(*) FROM meta.column_metric
        """
    )
    try:
        async with engine.connect() as connection:
            rows = (await connection.execute(sql)).mappings().all()
        return {row["item"]: row["total"] for row in rows}
    finally:
        await engine.dispose()


class MetadataIntegrationTest(unittest.TestCase):
    def test_meta_mysql_counts(self):
        counts = asyncio.run(get_meta_counts())
        self.assertEqual(counts["table_info"], 5)
        self.assertEqual(counts["column_info"], 24)
        self.assertEqual(counts["metric_info"], 2)
        self.assertEqual(counts["column_metric"], 2)

    def test_column_vector_count(self):
        data = get_json(
            "http://127.0.0.1:6333/collections/column_info_collection"
        )
        self.assertEqual(data["result"]["points_count"], 98)

    def test_metric_vector_count(self):
        data = get_json(
            "http://127.0.0.1:6333/collections/metric_info_collection"
        )
        self.assertEqual(data["result"]["points_count"], 8)

    def test_value_index_count(self):
        data = get_json("http://127.0.0.1:9200/value_index/_count")
        self.assertEqual(data["count"], 75)


if __name__ == "__main__":
    unittest.main()