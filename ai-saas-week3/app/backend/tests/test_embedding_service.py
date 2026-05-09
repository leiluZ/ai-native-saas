import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from src.rag.embedding_service import EmbeddingService


class TestEmbeddingService:
    """Embedding 服务测试"""

    @pytest.fixture
    def embedding_service(self):
        with patch.object(EmbeddingService, '_detect_device', return_value='cpu'):
            service = EmbeddingService()
            return service

    @pytest.mark.asyncio
    async def test_detect_device_cpu(self, embedding_service):
        """测试 CPU 设备检测"""
        assert embedding_service.device == "cpu"

    @pytest.mark.asyncio
    async def test_get_dimension(self, embedding_service):
        """测试向量维度"""
        assert embedding_service.get_dimension() == 1024

    @pytest.mark.asyncio
    async def test_encode_single_text(self, embedding_service):
        """测试单文本编码"""
        with patch.object(embedding_service, '_load_model'):
            with patch.object(embedding_service, '_encode_batch') as mock_encode:
                mock_encode.return_value = np.random.randn(1, 1024)

                result = await embedding_service.encode("测试文本")
                assert result.shape == (1, 1024)

    @pytest.mark.asyncio
    async def test_encode_multiple_texts(self, embedding_service):
        """测试多文本编码"""
        with patch.object(embedding_service, '_load_model'):
            with patch.object(embedding_service, '_encode_batch') as mock_encode:
                # 根据批次大小返回不同形状
                def side_effect(texts, normalize=True):
                    return np.random.randn(len(texts), 1024)
                mock_encode.side_effect = side_effect

                texts = ["文本1", "文本2", "文本3"]
                result = await embedding_service.encode(texts, batch_size=2)
                assert result.shape == (3, 1024)

    @pytest.mark.asyncio
    async def test_encode_queries(self, embedding_service):
        """测试查询编码（带指令前缀）"""
        with patch.object(embedding_service, '_load_model'):
            with patch.object(embedding_service, '_encode_batch') as mock_encode:
                mock_encode.return_value = np.random.randn(2, 1024)

                queries = ["查询1", "查询2"]
                result = await embedding_service.encode_queries(queries)
                assert result.shape == (2, 1024)

                # 验证调用了 encode 且文本包含指令前缀
                call_args = mock_encode.call_args[0][0]
                assert all("Represent this sentence" in text for text in call_args)

    @pytest.mark.asyncio
    async def test_encode_documents(self, embedding_service):
        """测试文档编码"""
        with patch.object(embedding_service, '_load_model'):
            with patch.object(embedding_service, '_encode_batch') as mock_encode:
                mock_encode.return_value = np.random.randn(2, 1024)

                docs = ["文档1", "文档2"]
                result = await embedding_service.encode_documents(docs)
                assert result.shape == (2, 1024)

    @pytest.mark.asyncio
    async def test_batch_processing(self, embedding_service):
        """测试批处理"""
        with patch.object(embedding_service, '_load_model'):
            with patch.object(embedding_service, '_encode_batch') as mock_encode:
                def side_effect(texts, normalize=True):
                    return np.random.randn(len(texts), 1024)
                mock_encode.side_effect = side_effect

                # 5个文本，batch_size=2，应该调用3次
                texts = ["文本1", "文本2", "文本3", "文本4", "文本5"]
                result = await embedding_service.encode(texts, batch_size=2)

                assert mock_encode.call_count == 3
                assert result.shape == (5, 1024)

    @pytest.mark.asyncio
    async def test_health_check_success(self, embedding_service):
        """测试健康检查成功"""
        with patch.object(embedding_service, '_load_model'):
            with patch.object(embedding_service, '_encode_batch') as mock_encode:
                mock_encode.return_value = np.random.randn(1, 1024)

                result = await embedding_service.health_check()
                assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, embedding_service):
        """测试健康检查失败"""
        with patch.object(embedding_service, '_load_model', side_effect=Exception("模型加载失败")):
            result = await embedding_service.health_check()
            assert result is False


class TestEmbeddingServiceDeviceDetection:
    """设备检测测试"""

    def test_detect_device_cuda(self):
        """测试 CUDA 检测"""
        with patch.object(EmbeddingService, '_detect_device', return_value='cuda'):
            service = EmbeddingService()
            assert service.device == "cuda"

    def test_detect_device_mps(self):
        """测试 MPS 检测"""
        with patch.object(EmbeddingService, '_detect_device', return_value='mps'):
            service = EmbeddingService()
            assert service.device == "mps"

    def test_detect_device_cpu(self):
        """测试 CPU 回退"""
        with patch.object(EmbeddingService, '_detect_device', return_value='cpu'):
            service = EmbeddingService()
            assert service.device == "cpu"
