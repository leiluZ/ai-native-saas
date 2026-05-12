#!/usr/bin/env python3
"""测试 Milvus 搜索功能"""
import pytest
import numpy as np


class TestMilvusSearch:
    """Milvus 搜索功能测试类"""

    def test_milvus_search_with_anns_field(self):
        """测试使用 anns_field 参数进行搜索"""
        try:
            from pymilvus import MilvusClient, DataType

            client = MilvusClient('http://milvus:19530')

            # 创建测试数据
            collection_name = 'test_search'
            if client.has_collection(collection_name):
                client.drop_collection(collection_name)

            schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field('id', DataType.VARCHAR, max_length=64, is_primary=True)
            schema.add_field('vector', DataType.FLOAT_VECTOR, dim=4)
            schema.add_field('text', DataType.VARCHAR, max_length=1000)

            client.create_collection(collection_name, schema=schema)

            # 创建索引
            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name="vector",
                index_type="HNSW",
                metric_type="COSINE",
                params={"M": 16, "efConstruction": 200}
            )
            client.create_index(collection_name, index_params)

            # 插入数据
            client.insert(collection_name, [{
                'id': 'test1',
                'vector': [0.1, 0.2, 0.3, 0.4],
                'text': 'test'
            }])

            # 加载集合并搜索
            client.load_collection(collection_name)

            # 测试搜索 - 使用 anns_field
            results = client.search(
                collection_name=collection_name,
                data=[[0.1, 0.2, 0.3, 0.4]],
                limit=1,
                anns_field='vector'
            )
            print('Search with anns_field succeeded:', results)
            assert len(results) == 1
            assert len(results[0]) == 1

            # 清理
            client.drop_collection(collection_name)

        except ImportError:
            pytest.skip("pymilvus not installed")
        except Exception as e:
            pytest.skip(f"Milvus not available: {e}")

    def test_milvus_search_without_anns_field(self):
        """测试不使用 anns_field 参数进行搜索"""
        try:
            from pymilvus import MilvusClient, DataType

            client = MilvusClient('http://milvus:19530')

            # 创建测试数据
            collection_name = 'test_search_no_anns'
            if client.has_collection(collection_name):
                client.drop_collection(collection_name)

            schema = client.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field('id', DataType.VARCHAR, max_length=64, is_primary=True)
            schema.add_field('vector', DataType.FLOAT_VECTOR, dim=4)
            schema.add_field('text', DataType.VARCHAR, max_length=1000)

            client.create_collection(collection_name, schema=schema)

            # 创建索引
            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name="vector",
                index_type="HNSW",
                metric_type="COSINE",
                params={"M": 16, "efConstruction": 200}
            )
            client.create_index(collection_name, index_params)

            # 插入数据
            client.insert(collection_name, [{
                'id': 'test1',
                'vector': [0.1, 0.2, 0.3, 0.4],
                'text': 'test'
            }])

            # 加载集合并搜索
            client.load_collection(collection_name)

            # 测试搜索 - 不使用 anns_field
            results = client.search(
                collection_name=collection_name,
                data=[[0.1, 0.2, 0.3, 0.4]],
                limit=1
            )
            print('Search without anns_field succeeded:', results)
            assert len(results) == 1
            assert len(results[0]) == 1

            # 清理
            client.drop_collection(collection_name)

        except ImportError:
            pytest.skip("pymilvus not installed")
        except Exception as e:
            pytest.skip(f"Milvus not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
