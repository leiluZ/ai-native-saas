import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VectorRecord:
    """向量记录"""

    id: str
    vector: np.ndarray
    text: str
    metadata: Dict[str, Any]


@dataclass
class SearchResult:
    """搜索结果"""

    id: str
    text: str
    metadata: Dict[str, Any]
    distance: float
    score: float


class VectorStore:
    """向量数据库服务，支持 HNSW/IVF_FLAT 索引"""

    def __init__(
        self,
        collection_name: str = "rag_documents",
        dimension: int = 1024,
        index_type: str = "HNSW",
        metric_type: str = "L2",
        host: str = "localhost",
        port: int = 19530,
    ):
        self.collection_name = collection_name
        self.dimension = dimension
        self.index_type = index_type
        self.metric_type = metric_type
        self.host = host
        self.port = port
        self._client = None
        self._collection = None

        logger.info(
            f"[VectorStore] Initializing - collection='{collection_name}', "
            f"dimension={dimension}, index_type='{index_type}'"
        )

    async def connect(self):
        """连接向量数据库"""
        try:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=f"http://{self.host}:{self.port}")
            logger.info(f"[VectorStore] Connected to Milvus at {self.host}:{self.port}")

            # 检查集合是否存在
            if self._client.has_collection(self.collection_name):
                self._client.load_collection(self.collection_name)
                logger.info(f"[VectorStore] Collection '{self.collection_name}' loaded")
            else:
                await self._create_collection()

        except ImportError:
            logger.warning(
                "[VectorStore] pymilvus not installed, using in-memory store"
            )
            self._client = InMemoryVectorStore(self.dimension)
        except Exception as e:
            logger.error(f"[VectorStore] Connection failed: {str(e)}")
            raise

    async def _create_collection(self):
        """创建集合和索引"""
        from pymilvus import DataType

        schema = self._client.create_schema(
            auto_id=False,
            enable_dynamic_field=True,
        )

        schema.add_field(
            field_name="id", datatype=DataType.VARCHAR, max_length=64, is_primary=True
        )
        schema.add_field(
            field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.dimension
        )
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="metadata", datatype=DataType.JSON)

        self._client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
        )

        # 创建索引
        index_params = self._client.prepare_index_params()

        if self.index_type == "HNSW":
            index_params.add_index(
                field_name="vector",
                index_type="HNSW",
                metric_type=self.metric_type,
                params={"M": 16, "efConstruction": 200},
            )
        elif self.index_type == "IVF_FLAT":
            index_params.add_index(
                field_name="vector",
                index_type="IVF_FLAT",
                metric_type=self.metric_type,
                params={"nlist": 128},
            )

        self._client.create_index(
            collection_name=self.collection_name,
            index_params=index_params,
        )

        self._client.load_collection(self.collection_name)
        logger.info(
            f"[VectorStore] Collection '{self.collection_name}' created with {self.index_type} index"
        )

    async def insert(
        self,
        records: List[VectorRecord],
        batch_size: int = 500,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> Dict[str, Any]:
        """
        批量插入向量记录

        Args:
            records: 向量记录列表
            batch_size: 批处理大小
            max_retries: 最大重试次数
            base_delay: 基础延迟（秒）

        Returns:
            插入结果统计
        """
        if not records:
            return {"inserted": 0, "errors": 0}

        logger.info(
            f"[VectorStore] Inserting {len(records)} records with batch_size={batch_size}"
        )

        total_inserted = 0
        total_errors = 0

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]

            for attempt in range(max_retries):
                try:
                    await self._insert_batch(batch)
                    total_inserted += len(batch)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(
                            f"[VectorStore] Batch insert failed after {max_retries} retries: {str(e)}"
                        )
                        total_errors += len(batch)
                    else:
                        delay = base_delay * (2**attempt)  # exponential backoff
                        logger.warning(
                            f"[VectorStore] Insert attempt {attempt + 1} failed, retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)

        logger.info(
            f"[VectorStore] Insert complete - inserted={total_inserted}, errors={total_errors}"
        )
        return {"inserted": total_inserted, "errors": total_errors}

    async def _insert_batch(self, records: List[VectorRecord]):
        """插入单个批次"""
        if isinstance(self._client, InMemoryVectorStore):
            # In-memory store
            await self._client.insert(records)
        else:
            # Milvus client
            data = [
                {
                    "id": r.id,
                    "vector": r.vector.tolist(),
                    "text": r.text,
                    "metadata": r.metadata,
                }
                for r in records
            ]
            self._client.insert(collection_name=self.collection_name, data=data)

    async def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        distance_threshold: Optional[float] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        向量搜索

        Args:
            query_vector: 查询向量
            top_k: 返回结果数量
            distance_threshold: 距离阈值过滤
            metadata_filter: 元数据过滤条件

        Returns:
            搜索结果列表
        """
        logger.info(
            f"[VectorStore] Searching - top_k={top_k}, "
            f"threshold={distance_threshold}, filter={metadata_filter}"
        )

        try:
            if hasattr(self._client, "search") and hasattr(
                self._client, "has_collection"
            ):
                # Milvus client
                results = self._client.search(
                    collection_name=self.collection_name,
                    data=[query_vector.tolist()],
                    limit=top_k,
                    output_fields=["id", "text", "metadata"],
                    filter=(
                        self._build_filter(metadata_filter) if metadata_filter else None
                    ),
                )

                search_results = []
                for hits in results:
                    for hit in hits:
                        distance = hit.get("distance", 0)
                        if (
                            distance_threshold is not None
                            and distance > distance_threshold
                        ):
                            continue

                        search_results.append(
                            SearchResult(
                                id=hit.get("id", ""),
                                text=hit.get("entity", {}).get("text", ""),
                                metadata=hit.get("entity", {}).get("metadata", {}),
                                distance=distance,
                                score=1 / (1 + distance),  # 转换距离为相似度分数
                            )
                        )

                logger.info(
                    f"[VectorStore] Search complete - found {len(search_results)} results"
                )
                return search_results
            else:
                # In-memory store
                return await self._client.search(
                    query_vector, top_k, distance_threshold, metadata_filter
                )

        except Exception as e:
            logger.error(f"[VectorStore] Search failed: {str(e)}")
            raise

    def _build_filter(self, metadata_filter: Dict[str, Any]) -> str:
        """构建 Milvus 过滤表达式"""
        conditions = []
        for key, value in metadata_filter.items():
            if isinstance(value, str):
                conditions.append(f'metadata["{key}"] == "{value}"')
            elif isinstance(value, (int, float)):
                conditions.append(f'metadata["{key}"] == {value}')
            elif isinstance(value, list):
                values_str = ", ".join(
                    [f'"{v}"' if isinstance(v, str) else str(v) for v in value]
                )
                conditions.append(f'metadata["{key}"] in [{values_str}]')

        return " and ".join(conditions) if conditions else ""

    async def delete(self, ids: List[str]) -> int:
        """删除记录"""
        if hasattr(self._client, "delete"):
            self._client.delete(collection_name=self.collection_name, ids=ids)
        else:
            await self._client.delete(ids)
        return len(ids)

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            if hasattr(self._client, "get_load_state"):
                state = self._client.get_load_state(self.collection_name)
                return state == "LoadStateLoaded"
            return True
        except Exception as e:
            logger.error(f"[VectorStore] Health check failed: {str(e)}")
            return False


class InMemoryVectorStore:
    """内存向量存储（备用实现）"""

    def __init__(self, dimension: int):
        self.dimension = dimension
        self.records: Dict[str, VectorRecord] = {}

    async def insert(self, records: List[VectorRecord]) -> Dict[str, Any]:
        for record in records:
            self.records[record.id] = record
        return {"inserted": len(records), "errors": 0}

    async def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        distance_threshold: Optional[float] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        results = []

        for record in self.records.values():
            # 元数据过滤
            if metadata_filter:
                match = True
                for key, value in metadata_filter.items():
                    if record.metadata.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            # 计算距离
            distance = np.linalg.norm(query_vector - record.vector)

            if distance_threshold is not None and distance > distance_threshold:
                continue

            results.append(
                SearchResult(
                    id=record.id,
                    text=record.text,
                    metadata=record.metadata,
                    distance=distance,
                    score=1 / (1 + distance),
                )
            )

        # 按距离排序
        results.sort(key=lambda x: x.distance)
        return results[:top_k]

    async def delete(self, ids: List[str]):
        for id in ids:
            self.records.pop(id, None)
